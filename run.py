"""Run the local reviewer interface. No account or API key is required."""
import os
from pathlib import Path
import runpy
import sys
root=Path(__file__).resolve().parent
os.environ.setdefault('PORT','7891')
os.environ['BEHAVIORLENS_HOST']='127.0.0.1'
os.environ.setdefault('BEHAVIORLENS_DATA',str(Path.home()/'.deviationlab-review'))
sys.path.insert(0,str(root/'web'))
runpy.run_path(str(root/'web/server.py'),run_name='__main__')
