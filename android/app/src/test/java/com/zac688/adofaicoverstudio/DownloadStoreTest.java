package com.zac688.adofaicoverstudio;

import static org.junit.Assert.*;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Base64;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class DownloadStoreTest {
    @Rule public TemporaryFolder temporary=new TemporaryFolder();

    @Test public void orderedChunksCreateExactlyTheOriginalFile() throws Exception {
        byte[] source=new byte[DownloadStore.CHUNK_BYTES*2+313];
        new java.util.Random(688).nextBytes(source);
        try(DownloadStore store=new DownloadStore(temporary.newFolder())) {
            DownloadStore.Transfer file=store.begin("中文封面.png","image/png",source.length);
            for(int offset=0;offset<source.length;offset+=DownloadStore.CHUNK_BYTES) {
                byte[] chunk=java.util.Arrays.copyOfRange(source,offset,Math.min(source.length,offset+DownloadStore.CHUNK_BYTES));
                assertEquals(offset+chunk.length,store.append(file.id,offset,Base64.getEncoder().encodeToString(chunk)));
            }
            assertEquals("中文封面.png",store.complete(file.id).name);
            assertArrayEquals(source,Files.readAllBytes(file.file.toPath()));
            store.discard(file.id);
            assertFalse(file.file.exists());
        }
    }

    @Test public void incompleteReorderedOrRepeatedChunksCannotBeExported() throws Exception {
        try(DownloadStore store=new DownloadStore(temporary.newFolder())) {
            DownloadStore.Transfer file=store.begin("style.json","application/json",6);
            String first=Base64.getEncoder().encodeToString(new byte[]{1,2,3});
            assertThrows(IllegalArgumentException.class,()->store.append(file.id,3,first));
            store.append(file.id,0,first);
            assertThrows(IllegalArgumentException.class,()->store.append(file.id,0,first));
            assertThrows(IllegalArgumentException.class,()->store.complete(file.id));
            assertEquals(3,file.file.length());
            store.append(file.id,3,first);
            store.complete(file.id);
            assertThrows(IllegalArgumentException.class,()->store.append(file.id,6,first));
            assertThrows(IllegalArgumentException.class,()->store.complete(file.id));
        }
    }

    @Test public void limitsAndFileTypesAreEnforcedBeforeWriting() throws Exception {
        File folder=temporary.newFolder();
        try(DownloadStore store=new DownloadStore(folder)) {
            assertThrows(IllegalArgumentException.class,()->store.begin("x.png","image/png",0));
            assertThrows(IllegalArgumentException.class,()->store.begin("x.png","image/png",100_000_001));
            assertThrows(IllegalArgumentException.class,()->store.begin("x.exe","application/octet-stream",1));
            assertEquals(0,folder.list().length);
            DownloadStore.Transfer file=store.begin("x.png","image/png",3);
            assertThrows(IllegalArgumentException.class,()->store.append(file.id,0,"!invalid!"));
            assertThrows(IllegalArgumentException.class,()->store.append(file.id,0,Base64.getEncoder().encodeToString(new byte[4])));
            assertEquals(0,file.file.length());
        }
    }

    @Test public void filenamesNeverChooseCachePathsAndUnicodeExtensionIsRetained() throws Exception {
        String name=DownloadStore.safeName("../目录\\unsafe\n封面.png");
        assertFalse(name.contains("/"));assertFalse(name.contains("\\"));assertFalse(name.contains("\n"));
        String longName=DownloadStore.safeName("封面🎵".repeat(100)+".adofai-text.json");
        assertTrue(longName.getBytes(StandardCharsets.UTF_8).length<=180);
        assertTrue(longName.endsWith(".adofai-text.json"));
        File folder=temporary.newFolder();
        try(DownloadStore store=new DownloadStore(folder)) {
            DownloadStore.Transfer file=store.begin("../../outside.png","image/png",1);
            assertEquals(folder.getCanonicalFile(),file.file.getParentFile());
            assertNotEquals("outside.png",file.file.getName());
            store.discard(file.id);
            assertFalse(file.file.exists());
        }
    }

    @Test public void cancelledTransferPreservesUnrelatedFilesAndCloseCleansOnlyItsOwnFiles() throws Exception {
        File folder=temporary.newFolder();
        File unrelated=new File(folder,"existing.png");
        Files.write(unrelated.toPath(),new byte[]{9,8,7});
        DownloadStore store=new DownloadStore(folder);
        DownloadStore.Transfer file=store.begin("new.svg","image/svg+xml;charset=utf-8",4);
        store.append(file.id,0,Base64.getEncoder().encodeToString(new byte[]{1,2}));
        store.close();
        assertFalse(file.file.exists());
        assertArrayEquals(new byte[]{9,8,7},Files.readAllBytes(unrelated.toPath()));
    }

    @Test public void completedSaveCanSurviveActivityRecreationWithoutTruncatingTheFile() throws Exception {
        File folder=temporary.newFolder();
        DownloadStore first=new DownloadStore(folder);
        DownloadStore.Transfer file=first.begin("封面.png","image/png",3);
        first.append(file.id,0,Base64.getEncoder().encodeToString(new byte[]{9,8,7}));
        first.complete(file.id);first.detach(file.id);first.close();
        try(DownloadStore resumed=new DownloadStore(folder)) {
            DownloadStore.Transfer restored=resumed.restore(file.id,file.name,file.mime,file.expected);
            resumed.pruneOrphans();
            assertArrayEquals(new byte[]{9,8,7},Files.readAllBytes(restored.file.toPath()));
            assertThrows(IllegalArgumentException.class,()->resumed.restore("../escape",file.name,file.mime,3));
            assertThrows(java.io.IOException.class,()->resumed.restore(file.id,file.name,file.mime,4));
            assertEquals(3,restored.file.length());
        }
    }

    @Test public void orphanCleanupCannotDeleteUnrelatedFilesOrThePendingTransfer() throws Exception {
        File folder=temporary.newFolder();
        File orphan=new File(folder,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.part");
        File existing=new File(folder,"actual-user-file.png");
        Files.write(orphan.toPath(),new byte[]{1});Files.write(existing.toPath(),new byte[]{2});
        try(DownloadStore store=new DownloadStore(folder)) {
            DownloadStore.Transfer active=store.begin("new.png","image/png",1);
            store.pruneOrphans();
            assertFalse(orphan.exists());assertTrue(active.file.exists());assertTrue(existing.exists());
        }
    }
}
