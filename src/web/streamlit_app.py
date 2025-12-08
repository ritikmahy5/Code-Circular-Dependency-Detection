import streamlit as st
import streamlit.components.v1 as components
import tempfile
import shutil
import os
import sys
import subprocess
from pathlib import Path
import zipfile
import json
import traceback
from typing import Optional, Dict, List, Any
import networkx as nx
import pandas as pd

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import your modules with correct class names
try:
    from src.parser.ast_parser import ImportExtractor
    from src.parser.resolver import ModuleResolver
    from src.parser.chunker import StructureAwareChunker, CodeChunk
    from src.graph.builder import DependencyGraphBuilder
    from src.graph.analyzer import CycleAnalyzer, CycleInfo, SeverityLevel
    from src.scoring.severity import SeverityScorer
    from src.visualization.graph_viz import DependencyVisualizer
    from src.explainer.generator import CycleExplainer
    from src.llm.factory import get_llm
    from src.knowledge.loader import PatternLoader
    from src.rag.dual_kb import DualKnowledgeRAG, RAGContext
    from src.chat import CodebaseChat
    from src.fixer import AutoFixer, FixStrategy
except ImportError as e:
    st.error(f"⚠️ Import error: {e}")
    st.info("Make sure you're running from the project root: `streamlit run src/web/app.py`")
    st.stop()

# Page config
st.set_page_config(
    page_title="Circular Dependency Detective",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main { padding-top: 2rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    .cycle-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .severity-critical { color: #ff4444; font-weight: bold; }
    .severity-high { color: #ff8800; font-weight: bold; }
    .severity-medium { color: #ffaa00; }
    .severity-low { color: #00aa00; }
    .metric-container {
        background: #f7f7f7;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .code-block {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 1rem;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'current_project' not in st.session_state:
    st.session_state.current_project = None
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None
if 'viz_html' not in st.session_state:
    st.session_state.viz_html = None
if 'viz_graph_hash' not in st.session_state:
    st.session_state.viz_graph_hash = None
if 'viz_path' not in st.session_state:
    st.session_state.viz_path = None
if 'github_url' not in st.session_state:
    st.session_state.github_url = None

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🔄 Circular Dependency Detective")
    st.markdown("**Detect and fix circular dependencies** using Tarjan's SCC algorithm + LLM-powered explanations")
with col2:
    if st.session_state.current_project:
        st.info(f"📁 Current: {st.session_state.current_project}")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # LLM Settings
    st.subheader("🤖 LLM Settings")
    enable_llm = st.checkbox("Enable LLM Explanations", value=True)
    
    if enable_llm:
        llm_provider = st.selectbox(
            "Provider",
            ["ollama", "openai", "claude"],
            help="Select LLM provider (Ollama runs locally)"
        )
        
        if llm_provider == "ollama":
            llm_model = st.text_input("Model", value="codellama:13b")
        elif llm_provider == "openai":
            api_key = st.text_input("API Key", type="password")
            llm_model = st.selectbox("Model", ["gpt-4", "gpt-3.5-turbo"])
        
        explanation_detail = st.slider(
            "Explanation Detail Level",
            min_value=1,
            max_value=5,
            value=3,
            help="Higher = more detailed explanations"
        )
    
    st.divider()
    
    # Analysis Settings
    st.subheader("🔍 Analysis Settings")
    
    min_cycle_size = st.number_input(
        "Minimum Cycle Size",
        min_value=2,
        max_value=10,
        value=2,
        help="Ignore cycles smaller than this"
    )
    
    include_tests = st.checkbox(
        "Include Test Files",
        value=False,
        help="Analyze test directories"
    )
    
    include_external = st.checkbox(
        "Track External Dependencies",
        value=False,
        help="Include third-party imports"
    )
    
    st.divider()
    
    # Quick Stats
    if st.session_state.analysis_results:
        st.subheader("📊 Quick Stats")
        results = st.session_state.analysis_results
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Cycles", results.get('total_cycles', 0))
            st.metric("Files Analyzed", results.get('files_analyzed', 0))
        with col2:
            st.metric("Critical Issues", results.get('critical_issues', 0))
            st.metric("Modules Affected", results.get('modules_affected', 0))

# Sample repositories for quick testing
SAMPLE_REPOS = {
    "Django (Complex)": "https://github.com/django/django",
    "FastAPI (Medium)": "https://github.com/tiangolo/fastapi",
    "Flask (Simple)": "https://github.com/pallets/flask",
    "Requests (Clean)": "https://github.com/psf/requests",
}

# Define all functions before they're used
def analyze_directory(project_path: Path, progress_bar=None):
    """Main analysis function that calls your modules"""
    
    if not progress_bar:
        progress_bar = st.progress(0)
    
    # Store the project path for chat initialization
    st.session_state.project_path = project_path
    
    # Clear old visualization when starting new analysis
    st.session_state.viz_html = None
    st.session_state.viz_graph_hash = None
    st.session_state.viz_path = None
    st.session_state.viz_show_all_deps_stored = None
    st.session_state.viz_highlight_cycles_only_stored = None
    
    try:
        # Step 1: Build dependency graph
        progress_bar.progress(20, text="Building dependency graph...")
        
        builder = DependencyGraphBuilder(project_path)
        graph = builder.build()  # build() returns the graph directly
        
        if graph.number_of_nodes() == 0:
            st.warning("No Python files found or could not build dependency graph!")
            return
        
        # Step 2: Detect cycles
        progress_bar.progress(40, text="Detecting circular dependencies...")
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()  # Returns list of CycleInfo objects
        
        if not cycles:
            st.success("✅ No circular dependencies found! Your code is clean.")
            st.session_state.analysis_results = {
                'total_cycles': 0,
                'files_analyzed': graph.number_of_nodes(),
                'cycles': [],
                'graph': graph
            }
            return
        
        # Step 3: Score severity
        progress_bar.progress(60, text="Calculating severity scores...")
        
        scorer = SeverityScorer(graph)
        severity_scores = scorer.score_all_cycles(cycles)  # Returns dict[cycle_id, SeverityScore]
        
        # Combine cycle info with severity scores
        scored_cycles = []
        for cycle in cycles:
            severity_score = severity_scores[cycle.cycle_id]
            scored_cycles.append({
                'cycle_id': cycle.cycle_id,
                'modules': cycle.files,
                'chain': cycle.chain,
                'severity': severity_score.numeric_score,
                'severity_level': severity_score.overall.value,
                'size': cycle.length,
                'has_type_checking_only': cycle.has_type_checking_only,
                'has_local_imports': cycle.has_local_imports,
                'coupling_density': cycle.coupling_density,
                'centrality_score': cycle.centrality_score,
                'priority_rank': severity_score.priority_rank,
                'estimated_effort': severity_score.estimated_effort,
                'edge_details': cycle.edge_details
            })
        
        # Sort by severity
        scored_cycles.sort(key=lambda x: -x['severity'])
        
        # Step 4: Generate explanations (if enabled and modules exist)
        # Comment out for now since we don't have these modules yet
        # if st.session_state.get('enable_llm', True):
        #     progress_bar.progress(85, text="Generating LLM explanations...")
        #     try:
        #         generator = ExplanationGenerator(llm_config={})
        #         for cycle_data in scored_cycles[:5]:
        #             explanation = generator.generate(cycle=cycle_data['modules'])
        #             cycle_data['explanation'] = explanation.get('explanation', '')
        #             cycle_data['suggestions'] = explanation.get('suggestions', [])
        #     except Exception as e:
        #         st.warning(f"Could not generate LLM explanations: {e}")
        
        # Step 5: Store results
        progress_bar.progress(100, text="Analysis complete!")
        
        critical_count = sum(1 for c in scored_cycles if c['severity'] >= 75)
        affected_modules = set()
        for cycle in scored_cycles:
            affected_modules.update(cycle['modules'])
        
        st.session_state.analysis_results = {
            'total_cycles': len(cycles),
            'files_analyzed': graph.number_of_nodes(),
            'critical_issues': critical_count,
            'modules_affected': len(affected_modules),
            'cycles': scored_cycles,
            'graph': graph,
            'raw_cycles': cycles  # Store original CycleInfo objects
        }
        
        st.session_state.graph_data = graph
        
        # Show summary
        st.success(f"""
        ✅ **Analysis Complete!**
        - **Files analyzed:** {graph.number_of_nodes()}
        - **Circular dependencies found:** {len(cycles)}
        - **Critical issues:** {critical_count}
        - **Affected modules:** {len(affected_modules)}
        """)
        
        st.info("💡 Switch to the **Analysis** tab to see detailed results")
        
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        if progress_bar:
            progress_bar.empty()

def analyze_github_repo(repo_url: str, branch: str = "main", depth: int = 1):
    """Clone and analyze a GitHub repository"""
    progress = st.progress(0, text="Initializing...")
    
    try:
        # Use persistent session directory instead of TemporaryDirectory
        session_id = st.session_state.get('session_id', id(st.session_state))
        st.session_state.session_id = session_id
        
        # Create persistent directory for this session
        persistent_dir = Path(tempfile.gettempdir()) / "cdd_sessions" / f"session_{session_id}"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a unique directory name for each clone to avoid conflicts
        import time
        repo_name = f"repo_{int(time.time() * 1000)}"  # Use milliseconds for uniqueness
        repo_path = persistent_dir / repo_name
        
        # Clean up old repo directories (keep only the most recent few)
        repo_dirs = sorted(
            [d for d in persistent_dir.iterdir() if d.is_dir() and d.name.startswith("repo")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        # Keep only the 3 most recent, delete older ones
        for old_repo in repo_dirs[3:]:
            try:
                shutil.rmtree(old_repo, ignore_errors=True)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clone repository
        progress.progress(20, text=f"Cloning repository from {repo_url}...")
        
        result = subprocess.run(
            ["git", "clone", "--depth", str(depth), "--branch", branch, repo_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            st.error(f"Git clone failed: {result.stderr}")
            return
        
        progress.progress(40, text="Repository cloned, starting analysis...")
        
        # Analyze - this will store project_path in session state
        st.session_state.current_project = repo_url.split('/')[-1]
        analyze_directory(repo_path, progress_bar=progress)
            
    except subprocess.TimeoutExpired:
        st.error("⏱️ Clone timeout. Try a smaller repository or increase timeout.")
    except Exception as e:
        st.error(f"Error: {str(e)}")
    finally:
        progress.empty()

def analyze_uploaded_file(uploaded_file):
    """Analyze uploaded file or archive"""
    progress = st.progress(0, text="Processing upload...")
    
    try:
        # Use persistent session directory instead of TemporaryDirectory
        session_id = st.session_state.get('session_id', id(st.session_state))
        st.session_state.session_id = session_id
        
        # Create persistent directory for this session
        persistent_dir = Path(tempfile.gettempdir()) / "cdd_sessions" / f"session_{session_id}"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up old project directories in this session
        for old_dir in persistent_dir.iterdir():
            if old_dir.is_dir():
                shutil.rmtree(old_dir, ignore_errors=True)
        
        tmppath = persistent_dir / "upload"
        tmppath.mkdir(exist_ok=True)
        
        if uploaded_file.name.endswith('.zip'):
            progress.progress(20, text="Extracting archive...")
            
            # Save and extract zip
            zip_path = tmppath / uploaded_file.name
            with open(zip_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmppath / "extracted")
            
            project_path = tmppath / "extracted"
            
            # Find Python files to determine root
            py_files = list(project_path.rglob("*.py"))
            if py_files:
                # Find common root
                common_parent = Path(os.path.commonpath([str(f.parent) for f in py_files]))
                project_path = common_parent
        else:
            # Single Python file
            progress.progress(20, text="Processing Python file...")
            file_path = tmppath / uploaded_file.name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            project_path = tmppath
        
        st.session_state.current_project = uploaded_file.name
        progress.progress(40, text="Starting analysis...")
        analyze_directory(project_path, progress_bar=progress)
            
    except Exception as e:
        st.error(f"Error processing upload: {str(e)}")
    finally:
        progress.empty()

# Define helper function before it's used
def process_chat_message(user_input: str):
    """Process a chat message and update the conversation."""
    
    # Add user message to history
    st.session_state.chat_history.append({
        'role': 'user',
        'content': user_input
    })
    
    # Get response from chat system
    with st.spinner("Thinking..."):
        try:
            # Get response from CodebaseChat
            response = st.session_state.chat_instance.ask_sync(user_input)
            
            # Add assistant message to history
            assistant_message = {
                'role': 'assistant',
                'content': response
            }
            
            # Check if response contains code blocks
            if "```python" in response:
                # Extract code blocks
                import re
                code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)
                if code_blocks:
                    assistant_message['code'] = code_blocks[0]
            
            st.session_state.chat_history.append(assistant_message)
            st.rerun()
            
        except Exception as e:
            st.error(f"Error getting response: {e}")
            st.info("Make sure Ollama is running: `ollama serve`")
            
            # Add error message to chat
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': f"I encountered an error: {str(e)}. Please make sure Ollama is running with `ollama serve` command."
            })
            st.rerun()

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 Input", 
    "🔍 Analysis", 
    "📊 Visualization", 
    "🔧 Fix Suggestions",
    "💬 AI Assistant"
])

# Tab 1: Input
with tab1:
    st.header("Select Input Source")
    
    input_method = st.radio(
        "Choose input method:",
        ["GitHub Repository", "Upload Files", "Local Directory", "Use Test Fixtures"],
        horizontal=True
    )
    
    if input_method == "GitHub Repository":
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Sample repo dropdown
            selected_sample = st.selectbox(
                "Quick select a sample repository:",
                ["Custom..."] + list(SAMPLE_REPOS.keys())
            )
            
            if selected_sample == "Custom...":
                repo_url = st.text_input(
                    "Enter GitHub repository URL:",
                    placeholder="https://github.com/username/repository"
                )
            else:
                repo_url = SAMPLE_REPOS[selected_sample]
                st.info(f"Selected: {repo_url}")
            
            # Store GitHub URL for clickable citations
            if repo_url:
                st.session_state.github_url = repo_url.rstrip('.git')
        
        with col2:
            st.markdown("### Options")
            branch = st.text_input("Branch", value="main")
            depth = st.number_input("Clone depth", value=1, min_value=1)
        
        if st.button("🚀 Analyze Repository", type="primary", disabled=not repo_url):
            analyze_github_repo(repo_url, branch, depth)
    
    elif input_method == "Upload Files":
        uploaded_file = st.file_uploader(
            "Upload Python files or ZIP archive",
            type=['py', 'zip'],
            accept_multiple_files=False,
            help="Upload individual .py files or a .zip archive"
        )
        
        if uploaded_file:
            st.info(f"📄 Uploaded: {uploaded_file.name} ({uploaded_file.size // 1024} KB)")
            
            if st.button("🔍 Analyze Upload", type="primary"):
                analyze_uploaded_file(uploaded_file)
    
    elif input_method == "Local Directory":
        local_path = st.text_input(
            "Enter local directory path:",
            placeholder="/path/to/your/python/project"
        )
        
        if st.button("📂 Analyze Directory", type="primary", disabled=not local_path):
            if os.path.exists(local_path):
                analyze_directory(Path(local_path))
            else:
                st.error(f"Path does not exist: {local_path}")
    
    else:  # Use Test Fixtures
        st.info("📁 Using test fixtures from `tests/fixtures/`")
        
        fixture_dir = Path(__file__).parent.parent.parent / "tests" / "fixtures"
        if fixture_dir.exists():
            fixtures = [d.name for d in fixture_dir.iterdir() if d.is_dir()]
            
            selected_fixture = st.selectbox("Select test fixture:", fixtures)
            
            if st.button("🧪 Analyze Fixture", type="primary"):
                analyze_directory(fixture_dir / selected_fixture)
        else:
            st.error("Test fixtures directory not found!")

def analyze_github_repo(repo_url: str, branch: str = "main", depth: int = 1):
    """Clone and analyze a GitHub repository"""
    progress = st.progress(0, text="Initializing...")
    
    try:
        # Use persistent session directory instead of TemporaryDirectory
        session_id = st.session_state.get('session_id', id(st.session_state))
        st.session_state.session_id = session_id
        
        # Create persistent directory for this session
        persistent_dir = Path(tempfile.gettempdir()) / "cdd_sessions" / f"session_{session_id}"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        
        # Use a unique directory name for each clone to avoid conflicts
        import time
        repo_name = f"repo_{int(time.time() * 1000)}"  # Use milliseconds for uniqueness
        repo_path = persistent_dir / repo_name
        
        # Clean up old repo directories (keep only the most recent few)
        repo_dirs = sorted(
            [d for d in persistent_dir.iterdir() if d.is_dir() and d.name.startswith("repo")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        # Keep only the 3 most recent, delete older ones
        for old_repo in repo_dirs[3:]:
            try:
                shutil.rmtree(old_repo, ignore_errors=True)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clone repository
        progress.progress(20, text=f"Cloning repository from {repo_url}...")
        
        result = subprocess.run(
            ["git", "clone", "--depth", str(depth), "--branch", branch, repo_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            st.error(f"Git clone failed: {result.stderr}")
            return
        
        progress.progress(40, text="Repository cloned, starting analysis...")
        
        # Analyze - this will store project_path in session state
        st.session_state.current_project = repo_url.split('/')[-1]
        analyze_directory(repo_path, progress_bar=progress)
            
    except subprocess.TimeoutExpired:
        st.error("⏱️ Clone timeout. Try a smaller repository or increase timeout.")
    except Exception as e:
        st.error(f"Error: {str(e)}")
    finally:
        progress.empty()

def analyze_uploaded_file(uploaded_file):
    """Analyze uploaded file or archive"""
    progress = st.progress(0, text="Processing upload...")
    
    try:
        # Use persistent session directory instead of TemporaryDirectory
        session_id = st.session_state.get('session_id', id(st.session_state))
        st.session_state.session_id = session_id
        
        # Create persistent directory for this session
        persistent_dir = Path(tempfile.gettempdir()) / "cdd_sessions" / f"session_{session_id}"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up old project directories in this session
        for old_dir in persistent_dir.iterdir():
            if old_dir.is_dir():
                shutil.rmtree(old_dir, ignore_errors=True)
        
        tmppath = persistent_dir / "upload"
        tmppath.mkdir(exist_ok=True)
        
        if uploaded_file.name.endswith('.zip'):
            progress.progress(20, text="Extracting archive...")
            
            # Save and extract zip
            zip_path = tmppath / uploaded_file.name
            with open(zip_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmppath / "extracted")
            
            project_path = tmppath / "extracted"
            
            # Find Python files to determine root
            py_files = list(project_path.rglob("*.py"))
            if py_files:
                # Find common root
                common_parent = Path(os.path.commonpath([str(f.parent) for f in py_files]))
                project_path = common_parent
        else:
            # Single Python file
            progress.progress(20, text="Processing Python file...")
            file_path = tmppath / uploaded_file.name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            project_path = tmppath
        
        st.session_state.current_project = uploaded_file.name
        progress.progress(40, text="Starting analysis...")
        analyze_directory(project_path, progress_bar=progress)
            
    except Exception as e:
        st.error(f"Error processing upload: {str(e)}")
    finally:
        progress.empty()

def analyze_directory(project_path: Path, progress_bar=None):
    """Main analysis function that calls your modules"""
    
    if not progress_bar:
        progress_bar = st.progress(0)
    
    try:
        # Step 1: Build dependency graph
        progress_bar.progress(20, text="Building dependency graph...")
        
        builder = DependencyGraphBuilder(project_path)
        graph = builder.build()  # build() returns the graph directly
        
        if graph.number_of_nodes() == 0:
            st.warning("No Python files found or could not build dependency graph!")
            return
        
        # Step 2: Detect cycles
        progress_bar.progress(40, text="Detecting circular dependencies...")
        
        analyzer = CycleAnalyzer(graph)
        cycles = analyzer.find_all_cycles()  # Returns list of CycleInfo objects
        
        if not cycles:
            st.success("✅ No circular dependencies found! Your code is clean.")
            st.session_state.analysis_results = {
                'total_cycles': 0,
                'files_analyzed': graph.number_of_nodes(),
                'cycles': [],
                'graph': graph
            }
            return
        
        # Step 3: Score severity
        progress_bar.progress(60, text="Calculating severity scores...")
        
        scorer = SeverityScorer(graph)
        severity_scores = scorer.score_all_cycles(cycles)  # Returns dict[cycle_id, SeverityScore]
        
        # Combine cycle info with severity scores
        scored_cycles = []
        for cycle in cycles:
            severity_score = severity_scores[cycle.cycle_id]
            scored_cycles.append({
                'cycle_id': cycle.cycle_id,
                'modules': cycle.files,
                'chain': cycle.chain,
                'severity': severity_score.numeric_score,
                'severity_level': severity_score.overall.value,
                'size': cycle.length,
                'has_type_checking_only': cycle.has_type_checking_only,
                'has_local_imports': cycle.has_local_imports,
                'coupling_density': cycle.coupling_density,
                'centrality_score': cycle.centrality_score,
                'priority_rank': severity_score.priority_rank,
                'estimated_effort': severity_score.estimated_effort,
                'edge_details': cycle.edge_details
            })
        
        # Sort by severity
        scored_cycles.sort(key=lambda x: -x['severity'])
        
        # Step 4: Generate explanations (if enabled and modules exist)
        # Comment out for now since we don't have these modules yet
        # if st.session_state.get('enable_llm', True):
        #     progress_bar.progress(85, text="Generating LLM explanations...")
        #     try:
        #         generator = ExplanationGenerator(llm_config={})
        #         for cycle_data in scored_cycles[:5]:
        #             explanation = generator.generate(cycle=cycle_data['modules'])
        #             cycle_data['explanation'] = explanation.get('explanation', '')
        #             cycle_data['suggestions'] = explanation.get('suggestions', [])
        #     except Exception as e:
        #         st.warning(f"Could not generate LLM explanations: {e}")
        
        # Step 5: Store results
        progress_bar.progress(100, text="Analysis complete!")
        
        critical_count = sum(1 for c in scored_cycles if c['severity'] >= 75)
        affected_modules = set()
        for cycle in scored_cycles:
            affected_modules.update(cycle['modules'])
        
        st.session_state.analysis_results = {
            'total_cycles': len(cycles),
            'files_analyzed': graph.number_of_nodes(),
            'critical_issues': critical_count,
            'modules_affected': len(affected_modules),
            'cycles': scored_cycles,
            'graph': graph,
            'raw_cycles': cycles  # Store original CycleInfo objects
        }
        
        st.session_state.graph_data = graph
        
        # Show summary
        st.success(f"""
        ✅ **Analysis Complete!**
        - **Files analyzed:** {graph.number_of_nodes()}
        - **Circular dependencies found:** {len(cycles)}
        - **Critical issues:** {critical_count}
        - **Affected modules:** {len(affected_modules)}
        """)
        
        st.info("💡 Switch to the **Analysis** tab to see detailed results")
        
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        if progress_bar:
            progress_bar.empty()

# Tab 2: Analysis Results
with tab2:
    st.header("🔍 Circular Dependencies Analysis")
    
    if not st.session_state.analysis_results:
        st.info("👈 Please analyze a project first using the Input tab")
    else:
        results = st.session_state.analysis_results
        
        if results['total_cycles'] == 0:
            st.success("🎉 No circular dependencies detected!")
        else:
            # Filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                severity_filter = st.slider(
                    "Minimum Severity",
                    min_value=0,
                    max_value=10,
                    value=5
                )
            
            with col2:
                size_filter = st.slider(
                    "Minimum Cycle Size",
                    min_value=2,
                    max_value=10,
                    value=2
                )
            
            with col3:
                sort_by = st.selectbox(
                    "Sort by",
                    ["Severity", "Size", "Module Count"]
                )
            
            # Filter cycles
            filtered_cycles = [
                c for c in results['cycles']
                if c['severity'] >= severity_filter and c['size'] >= size_filter
            ]
            
            # Sort cycles
            if sort_by == "Severity":
                filtered_cycles.sort(key=lambda x: x['severity'], reverse=True)
            elif sort_by == "Size":
                filtered_cycles.sort(key=lambda x: x['size'], reverse=True)
            
            st.subheader(f"Found {len(filtered_cycles)} cycles matching filters")
            
            # Add methodology explanation with citations
            with st.expander("ℹ️ How are circular dependencies detected and scored?"):
                st.markdown("### Detection Methodology")
                if st.session_state.github_url:
                    st.markdown(f"""
                    **Algorithm:** [Tarjan's Strongly Connected Components (SCC)]({st.session_state.github_url}/blob/main/src/graph/analyzer.py)
                    - Guarantees 100% cycle detection
                    - Finds all circular dependencies in O(V+E) time
                    - Implementation: `src/graph/analyzer.py`
                    
                    **Severity Scoring:** [Multi-factor Severity Calculator]({st.session_state.github_url}/blob/main/src/scoring/severity.py)
                    - Cycle length (how many files involved)
                    - Coupling density (how tightly connected)
                    - Node importance (centrality metrics)
                    - Implementation: `src/scoring/severity.py`
                    
                    **Pattern Matching:** [Refactoring Patterns]({st.session_state.github_url}/tree/main/knowledge_base/patterns)
                    - 4 documented refactoring patterns
                    - YAML-based pattern definitions
                    - Location: `knowledge_base/patterns/`
                    """)
                else:
                    st.markdown("""
                    **Algorithm:** Tarjan's Strongly Connected Components (SCC)
                    - Implementation: `src/graph/analyzer.py`
                    
                    **Severity Scoring:** Multi-factor Severity Calculator
                    - Implementation: `src/scoring/severity.py`
                    
                    **Pattern Matching:** Refactoring Patterns
                    - Location: `knowledge_base/patterns/`
                    """)
            
            # Display cycles
            for i, cycle in enumerate(filtered_cycles, 1):
                severity = cycle['severity']
                
                # Determine severity class
                if severity >= 8:
                    severity_class = "severity-critical"
                    emoji = "🔴"
                elif severity >= 6:
                    severity_class = "severity-high"
                    emoji = "🟠"
                elif severity >= 4:
                    severity_class = "severity-medium"
                    emoji = "🟡"
                else:
                    severity_class = "severity-low"
                    emoji = "🟢"
                
                with st.expander(
                    f"{emoji} **Cycle {i}** | Severity: {severity}/10 | Size: {cycle['size']} modules",
                    expanded=(i <= 3)  # Expand first 3
                ):
                    # Problem Type with Citation
                    st.markdown("**🔍 Problem Type:**")
                    if cycle['size'] == 1:
                        problem_type = "**Self-Cycle** (Module imports itself)"
                    elif cycle['size'] == 2:
                        problem_type = "**Direct Circular Dependency** (A → B → A)"
                    else:
                        problem_type = f"**Indirect Circular Dependency** (Chain of {cycle['size']} modules)"
                    
                    # Add citation to methodology
                    if st.session_state.github_url:
                        algo_url = f"{st.session_state.github_url}/blob/main/src/graph/analyzer.py"
                        severity_url = f"{st.session_state.github_url}/blob/main/src/scoring/severity.py"
                        st.markdown(f"{problem_type}")
                        st.markdown(f"📚 Detected using [Tarjan's SCC Algorithm]({algo_url}) | Scored by [Severity Calculator]({severity_url})")
                    else:
                        st.markdown(f"{problem_type}")
                        st.markdown(f"📚 Detection: `src/graph/analyzer.py` | Scoring: `src/scoring/severity.py`")
                    
                    # Cycle path
                    st.markdown("**📦 Module Path:**")
                    cycle_path = " → ".join(cycle['modules']) + " → " + cycle['modules'][0]
                    st.code(cycle_path, language="text")
                    
                    # Metrics row
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Severity", f"{severity}/100")
                    with col2:
                        st.metric("Modules", cycle['size'])
                    with col3:
                        st.metric("Complexity", "High" if severity >= 7 else "Medium" if severity >= 4 else "Low")
                    with col4:
                        st.metric("Priority", "Critical" if severity >= 8 else "High" if severity >= 6 else "Normal")
                    
                    # LLM Explanation
                    if 'explanation' in cycle and cycle['explanation']:
                        st.markdown("### 🤖 AI Analysis")
                        st.info(cycle['explanation'])
                    
                    # Suggestions
                    if 'suggestions' in cycle and cycle['suggestions']:
                        st.markdown("### 💡 Refactoring Suggestions")
                        
                        # Link to pattern sources
                        patterns_dir = Path(__file__).parent.parent.parent / "knowledge_base" / "patterns"
                        pattern_files = {
                            "extract interface": "extract_interface.yaml",
                            "lazy import": "lazy_import.yaml",
                            "type checking": "type_checking_guard.yaml",
                            "dependency injection": "dependency_injection.yaml"
                        }
                        
                        for j, suggestion in enumerate(cycle['suggestions'], 1):
                            st.markdown(f"{j}. {suggestion}")
                            
                            # Try to link to relevant pattern
                            suggestion_lower = suggestion.lower()
                            for pattern_name, pattern_file in pattern_files.items():
                                if pattern_name in suggestion_lower:
                                    if st.session_state.github_url:
                                        pattern_url = f"{st.session_state.github_url}/blob/main/knowledge_base/patterns/{pattern_file}"
                                        st.markdown(f"   📚 [View {pattern_name.title()} Pattern]({pattern_url})")
                                    else:
                                        st.markdown(f"   📚 Pattern source: `knowledge_base/patterns/{pattern_file}`")
                                    break
                    
                    # Show code context button
                    if st.button(f"View Code Context", key=f"code_{i}"):
                        st.markdown("### 📝 Code Context")
                        
                        # Deduplicate modules and show actual code from the cycle files
                        unique_modules = []
                        seen_paths = set()
                        for module_path in cycle['modules']:
                            # Normalize path for comparison
                            normalized = str(module_path).replace('\\', '/').lower()
                            if normalized not in seen_paths:
                                seen_paths.add(normalized)
                                unique_modules.append(module_path)
                        
                        # Also track displayed files to avoid showing the same file twice
                        displayed_files = set()
                        
                        for module_path in unique_modules[:3]:  # Show first 3 unique files to avoid clutter
                            # Normalize path separators and handle both relative and absolute paths
                            module_path_normalized = str(module_path).replace('\\', '/')
                            
                            if 'project_path' in st.session_state and st.session_state.project_path:
                                # Try joining with project path
                                project_path = Path(st.session_state.project_path)
                                # Handle both relative and absolute module paths
                                if Path(module_path_normalized).is_absolute():
                                    file_path = Path(module_path_normalized)
                                else:
                                    # Try different path combinations
                                    file_path = project_path / module_path_normalized
                                    if not file_path.exists():
                                        # Try with different separators
                                        file_path = project_path / module_path_normalized.replace('/', os.sep)
                            else:
                                file_path = Path(module_path_normalized)
                            
                            # Try to find the file if it doesn't exist at the expected location
                            if not file_path.exists() and 'project_path' in st.session_state and st.session_state.project_path:
                                project_path = Path(st.session_state.project_path)
                                # Search for the file by name in the project
                                filename = Path(module_path_normalized).name
                                for py_file in project_path.rglob(filename):
                                    if py_file.is_file():
                                        file_path = py_file
                                        break
                            
                            # Check if we've already displayed this file (by resolved path)
                            if file_path.exists() and file_path.is_file():
                                file_resolved = str(file_path.resolve())
                                if file_resolved in displayed_files:
                                    continue  # Skip if already displayed
                                displayed_files.add(file_resolved)
                                
                                # Create clickable link if GitHub URL is available
                                if st.session_state.github_url:
                                    # Extract relative path from file_path
                                    try:
                                        if 'project_path' in st.session_state and st.session_state.project_path:
                                            rel_path = file_path.relative_to(st.session_state.project_path)
                                        else:
                                            rel_path = file_path.name
                                        
                                        github_file_url = f"{st.session_state.github_url}/blob/main/{rel_path}"
                                        st.markdown(f"**File: [{module_path}]({github_file_url})** 📎")
                                    except:
                                        st.markdown(f"**File: `{module_path}`**")
                                else:
                                    st.markdown(f"**File: `{module_path}`** (local)")
                                
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        code_content = f.read()
                                    
                                    # Show just the imports section (first 20 lines or until first class/function)
                                    lines = code_content.split('\n')
                                    import_section = []
                                    line_num = 1
                                    for line in lines[:30]:  # Check first 30 lines
                                        # Add clickable line numbers for GitHub
                                        if st.session_state.github_url and 'import' in line:
                                            try:
                                                if 'project_path' in st.session_state and st.session_state.project_path:
                                                    rel_path = file_path.relative_to(st.session_state.project_path)
                                                else:
                                                    rel_path = file_path.name
                                                line_url = f"{st.session_state.github_url}/blob/main/{rel_path}#L{line_num}"
                                                import_section.append(f"# [L{line_num}]({line_url})")
                                            except:
                                                pass
                                        import_section.append(line)
                                        line_num += 1
                                        if line.strip().startswith('class ') or line.strip().startswith('def '):
                                            import_section.append("# ... rest of file ...")
                                            break
                                    
                                    st.code('\n'.join(import_section), language="python")
                                except Exception as e:
                                    st.error(f"Could not read file: {e}")
                            else:
                                st.warning(f"File not found: {module_path} (searched: {file_path})")

# Tab 3: Visualization
with tab3:
    st.header("📊 Dependency Graph Visualization")
    
    if not st.session_state.graph_data:
        st.info("👈 Please analyze a project first")
    else:
        # Visualization options (placed before generation so changes trigger regeneration)
        st.markdown("### Visualization Options")
        col1, col2 = st.columns(2)
        
        with col1:
            show_all_deps = st.checkbox(
                "Show all dependencies", 
                value=st.session_state.get('viz_show_all_deps', True),
                key="viz_show_all_deps",
                help="Show all dependency edges, not just cycle edges"
            )
        
        with col2:
            highlight_cycles_only = st.checkbox(
                "Highlight cycles only", 
                value=st.session_state.get('viz_highlight_cycles_only', False),
                key="viz_highlight_cycles_only",
                help="Show only cycle nodes and their immediate connections"
            )
        
        # Check if we need to regenerate visualization
        # Compare current checkbox values with previously stored values
        prev_show_all_deps = st.session_state.get('viz_show_all_deps_stored', None)
        prev_highlight_cycles_only = st.session_state.get('viz_highlight_cycles_only_stored', None)
        
        graph_changed = (
            st.session_state.get('viz_html') is None or 
            st.session_state.get('viz_graph_hash') != hash(str(st.session_state.graph_data.nodes())) or
            prev_show_all_deps != show_all_deps or
            prev_highlight_cycles_only != highlight_cycles_only
        )
        
        # Auto-generate Pyvis visualization if not already generated or settings changed
        if graph_changed:
            with st.spinner("🔄 Generating interactive visualization..."):
                try:
                    # Get the graph to visualize
                    G = st.session_state.graph_data
                    
                    # Filter graph if needed
                    if highlight_cycles_only and st.session_state.analysis_results and 'raw_cycles' in st.session_state.analysis_results:
                        # Create subgraph with only cycle nodes and their connections
                        cycle_nodes = set()
                        for cycle in st.session_state.analysis_results['raw_cycles']:
                            cycle_nodes.update(cycle.files)
                        
                        # Include nodes that connect to cycle nodes
                        if show_all_deps:
                            # Include all neighbors of cycle nodes
                            for node in list(cycle_nodes):
                                cycle_nodes.update(G.predecessors(node))
                                cycle_nodes.update(G.successors(node))
                        
                        # Create subgraph
                        G = G.subgraph(cycle_nodes).copy()
                    
                    visualizer = DependencyVisualizer(G)
                    
                    # Set cycles if they exist
                    if st.session_state.analysis_results and 'raw_cycles' in st.session_state.analysis_results:
                        # Filter cycles to only those in the current graph
                        filtered_cycles = []
                        graph_nodes = set(G.nodes())
                        for cycle in st.session_state.analysis_results['raw_cycles']:
                            if any(node in graph_nodes for node in cycle.files):
                                filtered_cycles.append(cycle)
                        visualizer.set_cycles(filtered_cycles)
                    
                    # Generate HTML file in a persistent location
                    viz_dir = Path(tempfile.gettempdir()) / "cdd_viz"
                    viz_dir.mkdir(exist_ok=True)
                    output_path = viz_dir / f"graph_{id(st.session_state.graph_data)}_{show_all_deps}_{highlight_cycles_only}.html"
                    
                    # Generate with better dimensions
                    visualizer.generate_html(output_path, height="900px", width="100%")
                    
                    # Read and inject legend into HTML
                    with open(output_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # Remove lib folder references since we're using CDN and embedding in Streamlit
                    # This makes the HTML fully standalone and doesn't require the lib folder
                    import re
                    html_content = re.sub(
                        r'<script src="lib/[^"]*"></script>\s*',
                        '',
                        html_content
                    )
                    html_content = re.sub(
                        r'<link[^>]*href="lib/[^"]*"[^>]*>\s*',
                        '',
                        html_content
                    )
                    
                    # Inject legend overlay into the HTML
                    legend_html = """
                    <div id="cdd-legend" style="
                        position: absolute;
                        bottom: 10px;
                        left: 10px;
                        background: rgba(255, 255, 255, 0.95);
                        border: 2px solid #333;
                        border-radius: 8px;
                        padding: 12px;
                        font-family: Arial, sans-serif;
                        font-size: 12px;
                        z-index: 1000;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        max-width: 300px;
                    ">
                        <div style="font-weight: bold; margin-bottom: 8px; font-size: 14px;">📋 Color Legend</div>
                        <div style="margin-bottom: 6px;">
                            <strong>Node Colors:</strong><br>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 16px; height: 16px; background-color: #97C2FC; border: 1px solid #333; border-radius: 3px; vertical-align: middle; margin-right: 6px;"></span>
                                Light Blue - Normal
                            </div>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 16px; height: 16px; background-color: #90EE90; border: 1px solid #333; border-radius: 3px; vertical-align: middle; margin-right: 6px;"></span>
                                Green - Low
                            </div>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 16px; height: 16px; background-color: #FFD700; border: 1px solid #333; border-radius: 3px; vertical-align: middle; margin-right: 6px;"></span>
                                Gold - Medium
                            </div>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 16px; height: 16px; background-color: #FFA500; border: 1px solid #333; border-radius: 3px; vertical-align: middle; margin-right: 6px;"></span>
                                Orange - High
                            </div>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 16px; height: 16px; background-color: #FF4500; border: 1px solid #333; border-radius: 3px; vertical-align: middle; margin-right: 6px;"></span>
                                Red - Critical
                            </div>
                        </div>
                        <div>
                            <strong>Edge Colors:</strong><br>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 30px; height: 2px; background-color: #848484; border: 1px solid #333; vertical-align: middle; margin-right: 6px;"></span>
                                Gray - Normal
                            </div>
                            <div style="margin: 3px 0;">
                                <span style="display: inline-block; width: 30px; height: 2px; background-color: #FF0000; border: 1px solid #333; vertical-align: middle; margin-right: 6px;"></span>
                                Red - Cycle
                            </div>
                        </div>
                    </div>
                    """
                    
                    import re
                    
                    # Make the card div position relative
                    html_content = re.sub(
                        r'<div class="card" style="([^"]*)"',
                        r'<div class="card" style="\1; position: relative;"',
                        html_content
                    )
                    
                    # Inject legend inside the card div, after mynetwork div
                    # Find: <div id="mynetwork"...></div> and inject legend after it
                    html_content = re.sub(
                        r'(<div id="mynetwork"[^>]*></div>)',
                        r'\1\n            ' + legend_html,
                        html_content,
                        count=1
                    )
                    
                    st.session_state.viz_html = html_content
                    st.session_state.viz_graph_hash = hash(str(st.session_state.graph_data.nodes()))
                    st.session_state.viz_path = str(output_path)
                    # Store the values that were used for this generation
                    st.session_state.viz_show_all_deps_stored = show_all_deps
                    st.session_state.viz_highlight_cycles_only_stored = highlight_cycles_only
                    
                except Exception as e:
                    st.error(f"Visualization generation error: {str(e)}")
                    st.code(traceback.format_exc())
        
        # Display the visualization
        if st.session_state.get('viz_html'):
            st.markdown("---")
            st.markdown("### 🎨 Interactive Dependency Graph")
            
            # Display mode selector
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                display_mode = st.radio(
                    "Display Mode:",
                    ["Embedded (800px)", "Full Screen", "Custom Height"],
                    horizontal=True,
                    key="viz_display_mode"
                )
            
            with col2:
                if display_mode == "Custom Height":
                    custom_height = st.slider("Height (pixels)", 600, 2000, 1200, 50)
                else:
                    custom_height = 800
            
            with col3:
                # Download button
                if st.session_state.get('viz_path'):
                    with open(st.session_state.viz_path, 'rb') as f:
                        st.download_button(
                            label="📥 Download",
                            data=f.read(),
                            file_name="dependency_graph.html",
                            mime="text/html",
                            help="Download as standalone HTML file"
                        )
            
            st.info("💡 **Drag nodes to rearrange** | **Hover for details** | **Zoom with mouse wheel** | **Click and drag to pan** | **Legend in bottom-left corner**")
            
            # Display based on mode
            if display_mode == "Full Screen":
                # Full screen mode - open in new tab
                st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 20px; 
                            border-radius: 10px; 
                            text-align: center;
                            margin: 20px 0;">
                    <h3 style="color: white; margin: 0 0 10px 0;">🚀 Full Screen Visualization</h3>
                    <p style="color: white; margin: 0 0 15px 0;">
                        Click the button below to open the interactive graph in a new browser tab for the best experience!
                    </p>
                """, unsafe_allow_html=True)
                
                # Create a temporary file that can be served
                if st.session_state.get('viz_path'):
                    # Show a button to open in new tab
                    st.markdown(f"""
                    <a href="file://{st.session_state.viz_path}" target="_blank" 
                       style="background-color: white; 
                              color: #667eea; 
                              padding: 12px 24px; 
                              text-decoration: none; 
                              border-radius: 5px; 
                              font-weight: bold;
                              display: inline-block;
                              cursor: pointer;">
                        🌐 Open Full Screen Graph
                    </a>
                    """, unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Also show embedded preview
                st.markdown("**Preview (Embedded):**")
                components.html(st.session_state.viz_html, height=600, scrolling=False)
                
            else:
                # Embedded mode with custom or default height
                height_to_use = custom_height if display_mode == "Custom Height" else 800
                
                # Display the HTML visualization with better styling
                components.html(st.session_state.viz_html, height=height_to_use, scrolling=False)
                
                # Add tips below
                st.markdown("""
                <div style="background: #f0f2f6; padding: 15px; border-radius: 8px; margin-top: 10px;">
                    <strong>🎯 Pro Tips:</strong>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        <li>Use <strong>Full Screen mode</strong> for the best visualization experience</li>
                        <li>Download the HTML file to view offline or share with team</li>
                        <li>Red edges indicate circular dependencies</li>
                        <li>Node size indicates centrality (importance)</li>
                        <li>Color indicates severity: 🟢 Low → 🟡 Medium → 🟠 High → 🔴 Critical</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

# Tab 4: Fix Suggestions
with tab4:
    st.header("🔧 Automated Fix Suggestions")
    
    if not st.session_state.analysis_results or st.session_state.analysis_results['total_cycles'] == 0:
        st.info("👈 No circular dependencies to fix")
    else:
        st.markdown("""
        This section provides automated refactoring suggestions and code fixes for detected circular dependencies.
        """)
        
        # Select cycle to fix
        cycles = st.session_state.analysis_results['cycles']
        
        cycle_options = [
            f"Cycle {i+1}: {' → '.join(c['modules'][:3])}... (Severity: {c['severity']:.1f}/100)"
            for i, c in enumerate(cycles)
        ]
        
        selected_cycle_idx = st.selectbox(
            "Select a cycle to fix:",
            range(len(cycle_options)),
            format_func=lambda x: cycle_options[x]
        )
        
        selected_cycle = cycles[selected_cycle_idx]
        
        st.markdown("### Selected Cycle Details")
        st.code(" → ".join(selected_cycle['chain']) + " → " + selected_cycle['chain'][0])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Severity", f"{selected_cycle['severity']:.1f}/100")
            st.metric("Module Count", selected_cycle['size'])
        with col2:
            st.metric("Priority Rank", selected_cycle.get('priority_rank', 'N/A'))
            st.metric("Estimated Effort", selected_cycle.get('estimated_effort', 'N/A'))
        
        # Fix strategies
        st.markdown("### 🛠️ Available Fix Strategies")
        
        fix_strategy = st.selectbox(
            "Choose refactoring strategy:",
            [
                ("Lazy Import", FixStrategy.LAZY_IMPORT),
                ("TYPE_CHECKING Guard", FixStrategy.TYPE_CHECKING),
                ("Extract Interface", FixStrategy.EXTRACT_INTERFACE),
                ("Merge Modules", FixStrategy.MERGE_MODULES)
            ],
            format_func=lambda x: x[0]
        )
        
        strategy_info = {
            FixStrategy.LAZY_IMPORT: """
            **Lazy Import Pattern**
            - Move imports inside functions
            - Defer loading until needed
            - Best for: Optional dependencies
            """,
            FixStrategy.TYPE_CHECKING: """
            **TYPE_CHECKING Guard**
            - Import only for type hints
            - No runtime dependency
            - Best for: Type annotations only
            """,
            FixStrategy.EXTRACT_INTERFACE: """
            **Extract Interface**
            - Create abstract base classes
            - Use dependency injection
            - Best for: Service classes
            """,
            FixStrategy.MERGE_MODULES: """
            **Merge Modules**
            - Combine tightly coupled modules
            - Simplify structure
            - Best for: Small, related modules
            """
        }
        
        st.info(strategy_info[fix_strategy[1]])
        
        if st.button("🔧 Generate Automated Fix", type="primary"):
            with st.spinner("Generating fix..."):
                try:
                    # Get the original CycleInfo object
                    if 'raw_cycles' in st.session_state.analysis_results:
                        raw_cycle = st.session_state.analysis_results['raw_cycles'][selected_cycle_idx]
                        
                        # Initialize AutoFixer
                        fixer = AutoFixer()
                        
                        # Generate fixes
                        fixes = fixer.generate_fix_sync(
                            cycle=raw_cycle,
                            project_path=Path(st.session_state.current_project) if st.session_state.current_project else Path("."),
                            strategy=fix_strategy[1]
                        )
                        
                        if fixes:
                            st.success(f"Generated {len(fixes)} fix(es)!")
                            
                            for i, fix in enumerate(fixes, 1):
                                with st.expander(f"Fix {i}: {fix.description}"):
                                    st.markdown(f"**File:** `{fix.file_path}`")
                                    st.markdown(f"**Strategy:** {fix.strategy.value}")
                                    st.markdown("**Diff:**")
                                    
                                    # Show diff
                                    diff = fixer._generate_diff(fix)
                                    st.code(diff, language="diff")
                                    
                                    if st.button(f"Apply Fix {i}", key=f"apply_fix_{i}"):
                                        result = fixer.apply_fixes([fix], dry_run=False)
                                        if result['applied']:
                                            st.success(f"Fix applied to {fix.file_path}")
                                        else:
                                            st.error("Failed to apply fix")
                        else:
                            st.warning("No fixes could be generated for this cycle")
                            
                except Exception as e:
                    st.error(f"Error generating fix: {str(e)}")
                    st.info("Make sure Ollama is running: `ollama serve`")

# Tab 5: AI Assistant
with tab5:
    st.header("💬 AI Assistant for Circular Dependencies")
    
    # Initialize chat in session state
    if 'chat_instance' not in st.session_state:
        st.session_state.chat_instance = None
    
    # Try to initialize chat if we have a project path and analysis results
    if (st.session_state.chat_instance is None and 
        'project_path' in st.session_state and 
        st.session_state.project_path):
        try:
            with st.spinner("Initializing AI Assistant..."):
                st.session_state.chat_instance = CodebaseChat(st.session_state.project_path)
                st.success("✅ AI Assistant ready!")
        except Exception as e:
            st.error(f"Could not initialize chat: {e}")
            st.info("Make sure Ollama is running: `ollama serve`")
            st.session_state.chat_instance = None
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Check if chat is available
    if st.session_state.chat_instance is None:
        st.info("👈 Please analyze a project first to enable the AI Assistant")
        st.markdown("""
        ### To enable the AI Assistant:
        1. Go to the **Input** tab
        2. Analyze a project (Local Directory or GitHub)
        3. Come back here after analysis completes
        4. Make sure Ollama is running (`ollama serve`)
        """)
    else:
        # Two-column layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Chat with AI about your circular dependencies")
            
            # Quick action buttons based on detected cycles
            if st.session_state.analysis_results and st.session_state.analysis_results['total_cycles'] > 0:
                st.markdown("### 🎯 Quick Questions")
                
                quick_questions = []
                
                if st.session_state.analysis_results['critical_issues'] > 0:
                    quick_questions.append(
                        f"How do I fix the {st.session_state.analysis_results['critical_issues']} critical circular dependencies?"
                    )
                
                if 'cycles' in st.session_state.analysis_results and len(st.session_state.analysis_results['cycles']) > 0:
                    worst_cycle = st.session_state.analysis_results['cycles'][0]
                    cycle_modules = ' → '.join(worst_cycle['chain'][:3]) + "..."
                    quick_questions.extend([
                        f"Explain why the cycle {cycle_modules} is problematic",
                        f"What's the best refactoring pattern for a {worst_cycle['size']}-module cycle?",
                        "Should I use dependency injection or lazy imports here?",
                        "What are the performance impacts of these circular dependencies?"
                    ])
                
                # Display quick question buttons in a grid
                cols = st.columns(2)
                for i, question in enumerate(quick_questions[:4]):
                    with cols[i % 2]:
                        if st.button(question, key=f"quick_{i}", use_container_width=True):
                            process_chat_message(question)
            
            # Chat messages display
            st.markdown("### 💭 Conversation")
            
            # Display chat history
            for message in st.session_state.chat_history:
                with st.chat_message(message['role']):
                    st.write(message['content'])
                    if 'code' in message:
                        st.code(message['code'], language='python')
            
            # Chat input
            user_input = st.chat_input("Ask about circular dependencies, refactoring patterns, or your specific cycles...")
            
            if user_input:
                process_chat_message(user_input)
        
        with col2:
            st.subheader("📊 Context")
            
            # Show current analysis context
            if st.session_state.analysis_results:
                st.info(f"""
                **Current Analysis:**
                - Total Cycles: {st.session_state.analysis_results['total_cycles']}
                - Critical Issues: {st.session_state.analysis_results['critical_issues']}
                - Files Analyzed: {st.session_state.analysis_results['files_analyzed']}
                - Modules Affected: {st.session_state.analysis_results['modules_affected']}
                """)
                
                # Show top cycles
                if 'cycles' in st.session_state.analysis_results:
                    st.markdown("**Top Cycles:**")
                    for i, cycle in enumerate(st.session_state.analysis_results['cycles'][:3], 1):
                        severity_emoji = "🔴" if cycle['severity'] > 75 else "🟠" if cycle['severity'] > 50 else "🟡"
                        st.text(f"{severity_emoji} Cycle {i}: {cycle['size']} modules")
            
            # Suggested topics
            st.markdown("### 💡 Topics")
            topics = [
                "Dependency injection",
                "Lazy import strategy",
                "Interface extraction",
                "Type checking guards",
                "Breaking service cycles",
                "Model-service separation",
                "Event-driven architecture",
                "Module merging"
            ]
            
            for topic in topics:
                if st.button(f"📖 {topic}", key=f"topic_{topic}", use_container_width=True):
                    process_chat_message(f"Explain {topic} for fixing circular dependencies")
            
            # Clear chat button
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
            else:
                st.info("👈 Please analyze a project first to enable the AI Assistant")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; padding: 2rem; color: #666;'>
    <p><strong>Circular Dependency Detective</strong></p>
    <p>Made by Karan, Ritik, Atharva & Akshay</p>
    <p>CS 6120 NLP | Northeastern University</p>
</div>
""", unsafe_allow_html=True)