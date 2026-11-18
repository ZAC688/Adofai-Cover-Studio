package com.zac688.adofaicoverstudio;

import static org.junit.Assert.*;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.provider.DocumentsContract;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.rule.ActivityTestRule;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class SystemFileTest {
    @Rule public ActivityTestRule<MainActivity> activity=new ActivityTestRule<>(MainActivity.class);
    private UiDevice device;

    @Before public void ready() throws Exception {
        assertTrue(activity.getActivity().getPackageName().endsWith(".debug"));
        assertTrue("Only emulator-owned files may be tested",Build.HARDWARE.contains("ranchu")||Build.HARDWARE.contains("goldfish"));
        device=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        long deadline=System.currentTimeMillis()+120_000;
        while(activity.getActivity().getRuntimePort()==0&&activity.getActivity().getStartupFailureForTests()==null&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertTrue(activity.getActivity().getStartupFailureForTests(),activity.getActivity().getRuntimePort()>0);
        deadline=System.currentTimeMillis()+60_000;
        while(!"true".equals(js("typeof window.adofaiSaveBlob==='function'"))&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertEquals("true",js("typeof window.adofaiSaveBlob==='function'"));
    }

    private String js(String script) throws Exception {
        CountDownLatch done=new CountDownLatch(1);String[] result={null};
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->activity.getActivity().getEditorWebView().evaluateJavascript(script,value->{result[0]=value;done.countDown();}));
        assertTrue(done.await(30,TimeUnit.SECONDS));return result[0];
    }

    private void begin() throws Exception {
        String name="adofai-native-test-"+UUID.randomUUID()+".png";
        js("(()=>{window.testSaveResult='waiting';const c=document.createElement('canvas');c.width=64;c.height=32;const ctx=c.getContext('2d');ctx.fillStyle='#cf9f50';ctx.fillRect(0,0,64,32);c.toBlob(blob=>adofaiSaveBlob(blob,"+JSONObject.quote(name)+").then(value=>testSaveResult=value).catch(error=>testSaveResult='error:'+error.message),'image/png');})()");
    }

    private void result(String expected) throws Exception {
        long deadline=System.currentTimeMillis()+30_000;
        String actual;
        do {actual=js("window.testSaveResult");if(actual.equals(JSONObject.quote(expected)))return;Thread.sleep(100);}while(System.currentTimeMillis()<deadline);
        assertEquals(JSONObject.quote(expected),actual);
    }

    private UiObject2 saveButton() {
        UiObject2 save=device.wait(Until.findObject(By.res(Pattern.compile(".*:id/action_menu_save"))),15_000);
        if(save==null)save=device.wait(Until.findObject(By.text(Pattern.compile("(?i)save|保存"))),5_000);
        assertNotNull("Android system document-save picker did not open",save);return save;
    }

    @Test public void realSystemSaveWritesAReadableFullPng() throws Exception {
        begin();UiObject2 save=saveButton();assertTrue(save.isEnabled());save.click();result("saved");
        Uri output=activity.getActivity().getLastSavedDocumentForTests();assertNotNull(output);
        try(java.io.InputStream stream=activity.getActivity().getContentResolver().openInputStream(output)) {
            Bitmap image=BitmapFactory.decodeStream(stream);assertNotNull(image);
            assertEquals(64,image.getWidth());assertEquals(32,image.getHeight());
            assertEquals(android.graphics.Color.rgb(207,159,80),image.getPixel(32,16));image.recycle();
        } finally {
            // The destination was created by this test with a unique name, on the emulator.
            DocumentsContract.deleteDocument(activity.getActivity().getContentResolver(),output);
        }
    }

    @Test public void realSystemCancelDoesNotReportSavedOrCloseTheEditor() throws Exception {
        begin();saveButton();
        // Back first hides the IME and then unwinds DocumentsUI's folder stack.
        // Complete the actual system cancel, stopping before sending Back to
        // the editor itself. No saved/cancelled result is mocked here.
        String editorPackage=activity.getActivity().getPackageName();
        for(int step=0;step<8&&!editorPackage.equals(device.getCurrentPackageName());step++) {
            device.pressBack();device.waitForIdle();
        }
        assertEquals("System picker must actually close before checking cancellation",editorPackage,device.getCurrentPackageName());
        result("cancelled");
        assertNull(activity.getActivity().getLastSavedDocumentForTests());
        assertEquals("true",js("Boolean(document.querySelector('.mobile-tabs'))"));
    }
}
