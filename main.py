# -*- coding: utf-8 -*-

import sys, os, json, glob, subprocess
parent_folder_path = os.path.abspath(os.path.dirname(__file__))
lib_path = os.path.join(parent_folder_path, 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)
sys.path.append(parent_folder_path)
sys.path.append(os.path.join(parent_folder_path, 'plugin'))

from flowlauncher import FlowLauncher

class UnrealHub(FlowLauncher):

    def get_app_data_path(self):
        return os.path.join(os.getenv('APPDATA'), 'unreal-hub')

    def load_json_data(self, filename, default=None):
        if default is None:
            default = {}
        path = os.path.join(self.get_app_data_path(), filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return default

    def get_git_branch(self, project_path):
        try:
            if not os.path.exists(os.path.join(os.path.dirname(project_path), '.git')):
                return None
            
            result = subprocess.check_output(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=os.path.dirname(project_path),
                stderr=subprocess.STDOUT,
                shell=True
            ).decode('utf-8').strip()
            return result
        except:
            return None

    def load_projects(self):
        projects_dict = {} 
        
        manual_projects = self.load_json_data('projects.json', [])
        raw_favorites = self.load_json_data('favorites.json', [])
        raw_tags_map = self.load_json_data('project-tags.json', {})
        raw_excluded = self.load_json_data('excluded.json', [])
        config = self.load_json_data('config.json', {})
        raw_overrides = config.get('projectOverrides', {})

        favorites = [os.path.normpath(p).lower() for p in raw_favorites if isinstance(p, str)]
        excluded = [os.path.normpath(p).lower() for p in raw_excluded if isinstance(p, str)]
        tags_map = {os.path.normpath(k).lower(): v for k, v in raw_tags_map.items()}
        normalized_overrides = {os.path.normpath(k).lower(): v for k, v in raw_overrides.items()}

        for p in manual_projects:
            if not isinstance(p, dict) or not p.get('path'): continue
            norm_path = os.path.normpath(p['path']).lower()
            if norm_path not in excluded:
                projects_dict[norm_path] = p

        for scan_path in config.get('projectPaths', []):
            if os.path.exists(scan_path):
                try:
                    subdirs = [os.path.join(scan_path, d) for d in os.listdir(scan_path) if os.path.isdir(os.path.join(scan_path, d))]
                    for subdir in subdirs:
                        uproject_files = glob.glob(os.path.join(subdir, '*.uproject'))
                        if uproject_files:
                            full_path = uproject_files[0]
                            norm_path = os.path.normpath(full_path).lower()
                            if norm_path in excluded or norm_path in projects_dict:
                                continue
                            
                            name = os.path.basename(full_path).replace('.uproject', '')
                            version = "Unknown"
                            try:
                                with open(full_path, 'r', encoding='utf-8') as pf:
                                    p_content = json.load(pf)
                                    version = p_content.get('EngineAssociation', 'Unknown')
                            except:
                                pass
                            
                            projects_dict[norm_path] = {
                                'name': name,
                                'path': full_path,
                                'version': version,
                                'lastModified': os.path.getmtime(full_path) * 1000
                            }
                except:
                    pass
        
        final_projects = []
        for norm_path, p in projects_dict.items():
            p['isFavorite'] = norm_path in favorites
            p['tags'] = tags_map.get(norm_path, [])
            
            if norm_path in normalized_overrides:
                override = normalized_overrides[norm_path]
                if override.get('name'):
                    p['name'] = override['name']
            final_projects.append(p)

        final_projects.sort(key=lambda x: (x.get('isFavorite', False), x.get('lastModified', 0)), reverse=True)
        return final_projects

    def load_engines(self):
        engines = []
        config = self.load_json_data('config.json', {})
        
        for path in config.get('enginePaths', []):
            if os.path.exists(path):
                if os.path.exists(os.path.join(path, 'Engine', 'Binaries')):
                     version = os.path.basename(path).replace('UE_', '')
                     engines.append({'version': version, 'path': path})
                else:
                     subdirs = [os.path.join(path, d) for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
                     for subdir in subdirs:
                         if os.path.basename(subdir).startswith('UE_'):
                             version = os.path.basename(subdir).replace('UE_', '')
                             engines.append({'version': version, 'path': subdir})
        return engines

    def format_project_result(self, project):
        name = project.get('name', 'Unknown')
        path = project.get('path', '')
        version = project.get('version', '')
        tags = project.get('tags', [])
        is_fav = project.get('isFavorite', False)
        
        title = ("⭐ " if is_fav else "") + name
        subtitle = f"UE {version} - {path}"
        if tags:
            subtitle += f" | Tags: {', '.join(tags)}"

        return {
            "Title": title,
            "SubTitle": subtitle,
            "IcoPath": "Images/app.png",
            "JsonRPCAction": {
                "method": "launch_project",
                "parameters": [path]
            },
            "ContextData": [path]
        }

    def query(self, query):
        results = []
        query_lower = query.lower()
        
        if query_lower.startswith('tags'):
            projects = self.load_projects()
            all_tags = {}
            for project in projects:
                for tag in project.get('tags', []):
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            
            sorted_tags = sorted(all_tags.items(), key=lambda x: x[0].lower())
            for tag, count in sorted_tags:
                results.append({
                    "Title": tag,
                    "SubTitle": f"{count} project{'s' if count > 1 else ''} with this tag",
                    "IcoPath": "Images/app.png"
                })
            
            if not results:
                results.append({
                    "Title": "No Tags Found",
                    "SubTitle": "Add tags to your projects in UnrealHub",
                    "IcoPath": "Images/app.png"
                })
            return results

        projects = self.load_projects()
        
        if query_lower.startswith('@'):
            target_tag = query_lower[1:].strip().lower()
            for project in projects:
                if any(t.lower() == target_tag for t in project.get('tags', [])):
                    results.append(self.format_project_result(project))
            return results

        if query_lower.startswith('engine'):
            engines = self.load_engines()
            for engine in engines:
                results.append({
                    "Title": f"Unreal Engine {engine['version']}",
                    "SubTitle": engine['path'],
                    "IcoPath": "Images/app.png",
                    "JsonRPCAction": {
                        "method": "launch_engine",
                        "parameters": [engine['path']]
                    },
                    "ContextData": [engine['path']]
                })
            return results

        query_terms = query_lower.split()
        for project in projects:
            name = project.get('name', 'Unknown')
            tags = project.get('tags', [])
            
            match_content = (name + " " + " ".join(tags)).lower()
            if all(term in match_content for term in query_terms):
                results.append(self.format_project_result(project))

        if not results and query:
            results.append({
                "Title": "No Projects Found",
                "SubTitle": "Try a different search term or check your configuration",
                "IcoPath": "Images/app.png"
            })
            
        return results

    def context_menu(self, data):
        path = data[0] if isinstance(data, list) else data
        menu = [
            {
                "Title": "Open in Explorer",
                "SubTitle": f"Reveal in Explorer: {path}",
                "IcoPath": "Images/app.png",
                "JsonRPCAction": {
                    "method": "open_explorer",
                    "parameters": [path] 
                }
            }
        ]

        branch = self.get_git_branch(path)
        if branch:
            menu.append({
                "Title": f"Git Branch: {branch}",
                "SubTitle": "Current active repository branch",
                "IcoPath": "Images/app.png",
                "JsonRPCAction": {
                    "method": "open_explorer",
                    "parameters": [path]
                }
            })
        return menu

    def launch_project(self, path):
        if os.path.exists(path):
            os.startfile(path)

    def launch_engine(self, path):
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
