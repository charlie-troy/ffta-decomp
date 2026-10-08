"""Resolve exact captured Python import closure, including explicit Git history."""
import ast
import hashlib
from pathlib import Path
import subprocess

from recovery_menu import require


def verify_source_versions(pins,entry,refs=(),directories=()):
    resolved={}
    for path,expected in pins.items():
        local=Path(path)
        data=local.read_bytes() if local.is_file() else None
        if data is None or hashlib.sha256(data).hexdigest()!=expected:
            data=None
            for directory in directories:
                candidate=Path(directory)/path
                if candidate.is_file():
                    captured=candidate.read_bytes()
                    if hashlib.sha256(captured).hexdigest()==expected:
                        data=captured;break
            for ref in refs:
                if data is not None:break
                proc=subprocess.run(['git','show',ref+':'+path],capture_output=True)
                if proc.returncode==0 and hashlib.sha256(proc.stdout).hexdigest()==expected:
                    data=proc.stdout;break
        require(data is not None,'captured source version unavailable: '+path)
        resolved[path]=data
    pending=[entry];found=set()
    while pending:
        name=pending.pop();path='tools/'+name+'.py'
        if name in found:continue
        found.add(name);require(path in resolved,'captured import closure missing: '+path)
        for node in ast.walk(ast.parse(resolved[path].decode('utf-8-sig'))):
            modules=([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else
                     [alias.name.split('.')[0] for alias in node.names] if isinstance(node,ast.Import) else [])
            pending.extend(module for module in modules if 'tools/'+module+'.py' in pins
                           or Path('tools',module+'.py').is_file())
    return sorted(found)
