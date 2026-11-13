import subprocess,unittest
import entry

class EntryTest(unittest.TestCase):
 def test_metadata_is_one_exact_scalar_not_overlapping_placeholder(self):
  plan=dict(nonce='f'*32,mode='COPY_ONLY_PERSISTENT_RECOVERY',real_root_authority=False,command_bytes=11396,command_md5='b'*32,command_crc=2059773043,context={'directory':'45826:52'})
  stage=dict(code_identity='45826:58:2090:11396:600:0:0:1',execution=False,core_rc=0,temp_delivery_absent=True,code_count=11396,code_md5='b'*32,code_crc=2059773043)
  text=entry.render(plan,stage,'/tmp/cmu-bench-copy-payload-'+'a'*32)
  line=next(x for x in text.splitlines() if "%d:%i:%Y:%s:%a:%u:%g:%h" in x)
  self.assertEqual(line,'test "$(stat -c \'%d:%i:%Y:%s:%a:%u:%g:%h\' "$p")" = 45826:58:2090:11396:600:0:0:1 || exit 73')
  self.assertNotIn('I/tmp/',text);self.assertNotIn('_VALUE',text)
  result=subprocess.run(['/bin/sh','-n'],input=text,text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
