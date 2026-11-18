package com.zac688.adofaicoverstudio;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Bounded, ordered transfer to private cache before the user chooses a destination. */
public final class DownloadStore implements AutoCloseable {
    public static final long MAX_BYTES = 100_000_000;
    public static final int CHUNK_BYTES = 192 * 1024;
    private final File directory;
    private final Map<String, Transfer> transfers = new HashMap<>();

    public static final class Transfer {
        public final String id, name, mime;
        public final File file;
        public final long expected;
        private long written;
        private FileOutputStream output;
        Transfer(String id, String name, String mime, File file, long expected) throws IOException {
            this(id,name,mime,file,expected,true);
        }
        Transfer(String id, String name, String mime, File file, long expected,boolean create) throws IOException {
            this.id=id; this.name=name; this.mime=mime; this.file=file; this.expected=expected;
            if(create)output=new FileOutputStream(file);
            else {
                if(!file.isFile()||file.length()!=expected)throw new IOException("待保存文件不完整，请重新导出");
                written=expected;
            }
        }
    }

    public DownloadStore(File directory) throws IOException {
        this.directory=directory.getCanonicalFile();
        if (!this.directory.isDirectory() && !this.directory.mkdirs()) throw new IOException("无法准备导出缓存");
    }

    public static String safeName(String name) {
        String clean=name.replaceAll("[\\p{Cntrl}\\\\/:*?\"<>|]", "_").trim().replaceAll("[. ]+$", "");
        if(clean.isEmpty()) clean="未命名文件";
        int dot=clean.lastIndexOf('.');
        String suffix=clean.endsWith(".adofai-text.json")?".adofai-text.json":clean.endsWith(".adofai-filters.json")?".adofai-filters.json":dot>0 && clean.length()-dot<=24 ? clean.substring(dot) : "";
        String base=suffix.isEmpty()?clean:clean.substring(0,clean.length()-suffix.length());
        while((base+suffix).getBytes(StandardCharsets.UTF_8).length>180 && !base.isEmpty()) {
            base=base.substring(0,base.offsetByCodePoints(base.length(),-1));
        }
        return base+suffix;
    }

    public synchronized Transfer begin(String name, String mime, long size) throws IOException {
        if(size<=0 || size>MAX_BYTES) throw new IllegalArgumentException("导出文件大小无效或超过 100 MB");
        if(transfers.size()>=2) throw new IllegalStateException("请先完成当前文件的保存");
        mime=mime.split(";",2)[0].trim().toLowerCase(java.util.Locale.ROOT);
        if(!mime.equals("image/png") && !mime.equals("image/svg+xml") && !mime.equals("application/json")) {
            throw new IllegalArgumentException("导出文件类型无效");
        }
        String id=UUID.randomUUID().toString().replace("-", "");
        Transfer transfer=new Transfer(id,safeName(name),mime,new File(directory,id+".part"),size);
        transfers.put(id,transfer);
        return transfer;
    }

    private Transfer require(String id) {
        Transfer transfer=transfers.get(id);
        if(transfer==null) throw new IllegalArgumentException("导出任务不存在");
        return transfer;
    }

    public synchronized long append(String id, long offset, String encoded) throws IOException {
        Transfer transfer=require(id);
        if(transfer.output==null || offset!=transfer.written) throw new IllegalArgumentException("导出数据顺序错误");
        if(encoded.length()>((CHUNK_BYTES+2)/3)*4) throw new IllegalArgumentException("导出数据块过大");
        byte[] bytes=Base64.getDecoder().decode(encoded);
        if(bytes.length>CHUNK_BYTES || transfer.written+bytes.length>transfer.expected) throw new IllegalArgumentException("导出文件长度不匹配");
        transfer.output.write(bytes);
        transfer.written+=bytes.length;
        return transfer.written;
    }

    public synchronized Transfer complete(String id) throws IOException {
        Transfer transfer=require(id);
        if(transfer.output==null || transfer.written!=transfer.expected) throw new IllegalArgumentException("导出文件未完整传输");
        transfer.output.getFD().sync();
        transfer.output.close();
        transfer.output=null;
        return transfer;
    }

    public synchronized Transfer get(String id) { return require(id); }

    public synchronized Transfer restore(String id,String name,String mime,long expected) throws IOException {
        if(!id.matches("[a-f0-9]{32}")||expected<=0||expected>MAX_BYTES)throw new IllegalArgumentException("待保存文件参数无效");
        if(!mime.equals("image/png")&&!mime.equals("image/svg+xml")&&!mime.equals("application/json"))throw new IllegalArgumentException("文件类型无效");
        Transfer transfer=new Transfer(id,safeName(name),mime,new File(directory,id+".part"),expected,false);
        transfers.put(id,transfer);
        return transfer;
    }

    public synchronized void detach(String id) {
        Transfer transfer=require(id);
        if(transfer.output!=null)throw new IllegalStateException("文件尚未完整传输");
        transfers.remove(id);
    }

    public synchronized void pruneOrphans() {
        File[] files=directory.listFiles();if(files==null)return;
        for(File file:files) {
            String name=file.getName();
            if(name.matches("[a-f0-9]{32}\\.part")&&!transfers.containsKey(name.substring(0,32)))file.delete();
        }
    }

    public synchronized void discard(String id) throws IOException {
        Transfer transfer=transfers.remove(id);
        if(transfer==null) return;
        if(transfer.output!=null) transfer.output.close();
        if(transfer.file.exists() && !transfer.file.delete()) throw new IOException("无法清理导出缓存");
    }

    @Override public synchronized void close() throws IOException {
        for(String id:new ArrayList<>(transfers.keySet())) discard(id);
    }
}
