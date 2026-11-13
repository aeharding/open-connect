import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"mapped-publication"))
from test_linked import LinkedTests
class DifferentSizePublication(LinkedTests):
 original_size=94058
 candidate_size=94717
if __name__=="__main__":unittest.main()
