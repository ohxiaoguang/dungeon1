import os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import nsoseg
# Decompress an NSO module (raw, LZ4 or ZBIC segments, see nsoseg.py) into a flat image: .text/.rodata/.data plus the zero pages of .bss, at the module's memory offsets.
d=open(sys.argv[1],'rb').read()
img,header=nsoseg.image(d,nsoseg.parse(d),bss=True)
open(sys.argv[2],'wb').write(img)
print([hex(x) for s in header.segments for x in (s.file_offset,s.memory_offset,s.size)],hex(header.bss),'moduleid',header.build_id.hex(),nsoseg.describe(header))
