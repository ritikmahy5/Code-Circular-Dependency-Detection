import streamlit as st
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
    "Test Project (Simple)": "https://github.com/yourusername/test-cycles",
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
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            
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
            
            # Analyze
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
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
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
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            
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
            
            # Analyze
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
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
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
                        for j, suggestion in enumerate(cycle['suggestions'], 1):
                            st.markdown(f"{j}. {suggestion}")
                    
                    # Show code context button
                    if st.button(f"View Code Context", key=f"code_{i}"):
                        st.markdown("### 📝 Code Context")
                        # This would show actual code from the modules
                        st.code("# Code preview would go here", language="python")

# Tab 3: Visualization
with tab3:
    st.header("📊 Dependency Graph Visualization")
    
    if not st.session_state.graph_data:
        st.info("👈 Please analyze a project first")
    else:
        # Visualization options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            viz_type = st.selectbox(
                "Visualization Type",
                ["Interactive Network", "Pyvis Graph", "Matrix View"]
            )
        
        with col2:
            show_all_deps = st.checkbox("Show all dependencies", value=False)
            highlight_cycles = st.checkbox("Highlight cycles only", value=True)
        
        with col3:
            layout = st.selectbox(
                "Graph Layout",
                ["Spring", "Circular", "Hierarchical", "Random"]
            )
        
        if st.button("🎨 Generate Visualization", type="primary"):
            with st.spinner("Creating visualization..."):
                try:
                    if viz_type == "Pyvis Graph":
                        # Use the built-in DependencyVisualizer
                        import tempfile
                        from pathlib import Path
                        
                        visualizer = DependencyVisualizer(st.session_state.graph_data)
                        
                        # Set cycles if they exist
                        if 'raw_cycles' in st.session_state.analysis_results:
                            visualizer.set_cycles(st.session_state.analysis_results['raw_cycles'])
                        
                        # Generate HTML file
                        with tempfile.NamedTemporaryDirectory() as tmpdir:
                            output_path = Path(tmpdir) / "graph.html"
                            visualizer.generate_html(output_path, height="600px")
                            
                            # Read and display HTML
                            with open(output_path, 'r') as f:
                                html_content = f.read()
                            
                            components.html(html_content, height=650)
                    
                    elif viz_type == "Interactive Network":
                        # Create interactive graph using networkx and plotly
                        import plotly.graph_objects as go
                        
                        G = st.session_state.graph_data
                        
                        # Get cycle edges if available
                        cycle_edges = set()
                        cycle_nodes = set()
                        if 'cycles' in st.session_state.analysis_results:
                            for cycle_data in st.session_state.analysis_results['cycles']:
                                chain = cycle_data.get('chain', cycle_data['modules'])
                                cycle_nodes.update(cycle_data['modules'])
                                for i in range(len(chain) - 1):
                                    cycle_edges.add((chain[i], chain[i + 1]))
                        
                        # Generate layout
                        if layout == "Spring":
                            pos = nx.spring_layout(G)
                        elif layout == "Circular":
                            pos = nx.circular_layout(G)
                        elif layout == "Hierarchical":
                            pos = nx.planar_layout(G) if nx.is_planar(G) else nx.spring_layout(G)
                        else:
                            pos = nx.random_layout(G)
                        
                        # Create Plotly figure
                        edge_trace = []
                        for edge in G.edges():
                            x0, y0 = pos[edge[0]]
                            x1, y1 = pos[edge[1]]
                            
                            color = 'red' if edge in cycle_edges else 'gray'
                            width = 3 if edge in cycle_edges else 1
                            
                            edge_trace.append(
                                go.Scatter(
                                    x=[x0, x1, None],
                                    y=[y0, y1, None],
                                    line=dict(width=width, color=color),
                                    hoverinfo='none',
                                    mode='lines'
                                )
                            )
                        
                        # Node trace
                        node_x = []
                        node_y = []
                        node_text = []
                        node_color = []
                        
                        for node in G.nodes():
                            x, y = pos[node]
                            node_x.append(x)
                            node_y.append(y)
                            node_text.append(node.split('/')[-1] if '/' in node else node)
                            node_color.append('red' if node in cycle_nodes else 'lightblue')
                        
                        node_trace = go.Scatter(
                            x=node_x, y=node_y,
                            mode='markers+text',
                            hoverinfo='text',
                            text=node_text,
                            hovertext=[node for node in G.nodes()],
                            textposition="top center",
                            marker=dict(
                                size=12,
                                color=node_color,
                                line=dict(width=2)
                            )
                        )
                        
                        fig = go.Figure(
                            data=edge_trace + [node_trace],
                            layout=go.Layout(
                                showlegend=False,
                                hovermode='closest',
                                margin=dict(b=0, l=0, r=0, t=0),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                height=600
                            )
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                    elif viz_type == "Matrix View":
                        # Create adjacency matrix
                        st.info("Dependency Matrix View")
                        
                        nodes = list(G.nodes())
                        matrix = []
                        
                        for node1 in nodes:
                            row = []
                            for node2 in nodes:
                                if G.has_edge(node1, node2):
                                    row.append(1)
                                else:
                                    row.append(0)
                            matrix.append(row)
                        
                        # Create DataFrame with shortened labels
                        short_labels = [n.split('/')[-1] if '/' in n else n for n in nodes]
                        df = pd.DataFrame(matrix, index=short_labels, columns=short_labels)
                        
                        # Display with color coding
                        st.dataframe(
                            df.style.background_gradient(cmap='RdYlBu_r', vmin=0, vmax=1),
                            use_container_width=True
                        )
                    
                except Exception as e:
                    st.error(f"Visualization error: {str(e)}")
                    st.code(traceback.format_exc())

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