import hashlib
import struct

import pefile


def ico_images(path):
    raw=path.read_bytes();reserved,kind,count=struct.unpack_from('<HHH',raw)
    assert (reserved,kind,count)==(0,1,7)
    result=[]
    for i in range(count):
        w,h,colors,reserved,planes,bpp,size,offset=struct.unpack_from('<BBBBHHII',raw,6+i*16)
        result.append(((w or 256,h or 256),raw[offset:offset+size]))
    return result


def assert_pe_icon(binary,icon):
    with pefile.PE(str(binary)) as pe:
        entries={e.id:e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        assert 3 in entries and 14 in entries,'Windows executable must have image and icon-group resources'
        images=[]
        for entry in entries[3].directory.entries:
            data=entry.directory.entries[0].data.struct
            images.append(pe.get_data(data.OffsetToData,data.Size))
        wanted=ico_images(icon)
        assert {hashlib.sha256(data).hexdigest() for data in images}=={hashlib.sha256(data).hexdigest() for _,data in wanted}
        group=entries[14].directory.entries[0].directory.entries[0].data.struct
        payload=pe.get_data(group.OffsetToData,group.Size)
        assert struct.unpack_from('<HHH',payload)==(0,1,7)
