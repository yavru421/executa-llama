import os, importlib.util
p = os.path.join(os.path.dirname(__file__), '..', 'plugins')
p = os.path.abspath(p)
print('plugins path:', p)
modules = {}
if not os.path.isdir(p):
    print('plugins folder not found')
    raise SystemExit(1)
for fname in os.listdir(p):
    if not fname.endswith('.py'):
        continue
    fpath = os.path.join(p, fname)
    spec = importlib.util.spec_from_file_location(fname[:-3], fpath)
    if spec is None or spec.loader is None:
        print('Could not load spec for', fname)
        continue
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        for attr in dir(module):
            if attr.startswith('tool_') and callable(getattr(module, attr)):
                modules[attr] = getattr(module, attr)
    except Exception as e:
        print('Failed to import', fname, e)
print('Registered tool functions:', list(modules.keys()))
