# -*- coding: utf-8 -*-

import sys, os, json, glob, subprocess
parent_folder_path = os.path.abspath(os.path.dirname(__file__))
sys.path.append(parent_folder_path)
sys.path.append(os.path.join(parent_folder_path, 'lib'))
sys.path.append(os.path.join(parent_folder_path, 'plugin'))

from flowlauncher import FlowLauncher
import webbrowser

class UnrealHub(FlowLauncher):

    def get_app_data_path(self):
        return os.path.join(os.getenv('APPDATA'), 'unreal-hub')

    def load_projects(self):
        projects = []
        app_data = self.get_app_data_path()
        projects_file = os.path.join(app_data, 'projects.json')
        
        # Load manual projects
        if os.path.exists(projects_file):
            try:
                with open(projects_file, 'r', encoding='utf-8') as f:
                    projects = json.load(f)
            except:
                pass

        # Load config and scan paths
        config_file = os.path.join(app_data, 'config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Basic scan implementation (non-recursive for now to match main.ts depth 1)
                for path in config.get('projectPaths', []):
                    if os.path.exists(path):
                        # Find .uproject files in immediate subdirectories
                        # e.g. D:/Projects/MyGame/MyGame.uproject
                        subdirs = [os.path.join(path, d) for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                        for subdir in subdirs:
                            uproject_files = glob.glob(os.path.join(subdir, '*.uproject'))
                            if uproject_files:
                                full_path = uproject_files[0]
                                # Check if already in projects
                                if not any(p['path'] == full_path for p in projects):
                                    name = os.path.basename(full_path).replace('.uproject', '')
                                    # Get version if possible
                                    version = "Unknown"
                                    try:
                                        with open(full_path, 'r', encoding='utf-8') as pf:
                                            p_content = json.load(pf)
                                            version = p_content.get('EngineAssociation', 'Unknown')
                                    except:
                                        pass
                                    
                                    projects.append({
                                        'name': name,
                                        'path': full_path,
                                        'version': version,
                                        'lastModified': os.path.getmtime(full_path) * 1000
                                    })
            except Exception as e:
                pass
        
        # Sort by last modified descending
        projects.sort(key=lambda x: x.get('lastModified', 0), reverse=True)
        return projects

    def load_engines(self):
        engines = []
        app_data = self.get_app_data_path()
        config_file = os.path.join(app_data, 'config.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for path in config.get('enginePaths', []):
                    if os.path.exists(path):
                        # Check if path itself is an engine or contains engines
                        if os.path.exists(os.path.join(path, 'Engine', 'Binaries')):
                             version = os.path.basename(path).replace('UE_', '')
                             engines.append({'version': version, 'path': path})
                        else:
                             # Check subdirectories
                             subdirs = [os.path.join(path, d) for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                             for subdir in subdirs:
                                 if os.path.basename(subdir).startswith('UE_'):
                                     version = os.path.basename(subdir).replace('UE_', '')
                                     engines.append({'version': version, 'path': subdir})
            except:
                pass
        return engines

    def query(self, query):
        results = []
        
        # 'ue engine' command
        if query.lower().startswith('engine'):
            engines = self.load_engines()
            for engine in engines:
                results.append({
                    "Title": f"Unreal Engine {engine['version']}",
                    "SubTitle": engine['path'],
                    "IcoPath": "Images/app.png",
                    "JsonRPCAction": {
                        "method": "launch_engine",
                        "parameters": [engine['path']]
                    }
                })
            if not results:
                 results.append({
                    "Title": "No Engines Found",
                    "SubTitle": "Check your UnrealHub configuration",
                    "IcoPath": "Images/app.png"
                })
            return results

        # Project search
        projects = self.load_projects()
        query_terms = query.lower().split()
        
        for project in projects:
            name = project.get('name', 'Unknown')
            path = project.get('path', '')
            version = project.get('version', '')
            
            # Simple keyword matching
            if all(term in name.lower() for term in query_terms):
                results.append({
                    "Title": name,
                    "SubTitle": f"UE {version} - {path}",
                    "IcoPath": "Images/app.png",
                    "JsonRPCAction": {
                        "method": "launch_project",
                        "parameters": [path]
                    }
                })

        if not results and query:
            results.append({
                "Title": "No Projects Found",
                "SubTitle": "Try a different search term",
                "IcoPath": "Images/app.png"
            })
            
        return results

    def context_menu(self, data):
        return [
            {
                "Title": "Open in Explorer",
                "SubTitle": "Reveal project file in Windows Explorer",
                "IcoPath": "Images/app.png",
                "JsonRPCAction": {
                    "method": "open_explorer",
                    "parameters": [data[0] if isinstance(data, list) else data] 
                }
            }
        ]

    def launch_project(self, path):
        if os.path.exists(path):
            os.startfile(path)

    def launch_engine(self, path):
        # Try standard locations for executable
        possible_exes = [
            os.path.join(path, 'Engine', 'Binaries', 'Win64', 'UnrealEditor.exe'),
            os.path.join(path, 'Engine', 'Binaries', 'Win64', 'UE4Editor.exe')
        ]
        
        for exe in possible_exes:
            if os.path.exists(exe):
                os.startfile(exe)
                return

    def open_explorer(self, path):
        if os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{path}"')

if __name__ == "__main__":
    UnrealHub()
