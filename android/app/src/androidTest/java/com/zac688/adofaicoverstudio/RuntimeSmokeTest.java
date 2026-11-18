package com.zac688.adofaicoverstudio;

import static org.junit.Assert.*;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Build;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.rule.ActivityTestRule;
import com.chaquo.python.Python;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.Proxy;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class RuntimeSmokeTest {
    @Rule public ActivityTestRule<MainActivity> activity=new ActivityTestRule<>(MainActivity.class);
    private String address,token;

    @Before public void ready() throws Exception {
        assertTrue("Native test harness must target the separate debug application",activity.getActivity().getPackageName().endsWith(".debug"));
        assertTrue("Only the isolated emulator may run these tests",Build.HARDWARE.contains("ranchu")||Build.HARDWARE.contains("goldfish"));
        long deadline=System.currentTimeMillis()+120_000;
        while(activity.getActivity().getRuntimePort()==0 && activity.getActivity().getStartupFailureForTests()==null && System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertTrue("Offline Android runtime did not start: "+activity.getActivity().getStartupFailureForTests(),activity.getActivity().getRuntimePort()>0);
        address="http://127.0.0.1:"+activity.getActivity().getRuntimePort();
        token=new JSONObject(request("GET","/api/session",null,null)).getString("token");
    }

    private byte[] read(InputStream input) throws Exception {
        try(InputStream stream=input;ByteArrayOutputStream bytes=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[65536];int count;
            while((count=stream.read(buffer))!=-1)bytes.write(buffer,0,count);
            return bytes.toByteArray();
        }
    }

    private byte[] asset(String name) throws Exception {
        return read(InstrumentationRegistry.getInstrumentation().getContext().getAssets().open(name));
    }

    private String request(String method,String path,byte[] body,String mime) throws Exception {
        return new String(binaryRequest(method,path,body,mime),StandardCharsets.UTF_8);
    }

    private byte[] binaryRequest(String method,String path,byte[] body,String mime) throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL(address+path).openConnection(Proxy.NO_PROXY);
        try {
            connection.setRequestMethod(method);connection.setConnectTimeout(10_000);connection.setReadTimeout(60_000);
            if(body!=null) {
                connection.setDoOutput(true);connection.setRequestProperty("Content-Type",mime);
                connection.setRequestProperty("x-editor-token",token);connection.setFixedLengthStreamingMode(body.length);
                try(var output=connection.getOutputStream()){output.write(body);}
            }
            int status=connection.getResponseCode();
            byte[] result=read(status<400?connection.getInputStream():connection.getErrorStream());
            assertEquals(new String(result,StandardCharsets.UTF_8),200,status);
            return result;
        } finally {connection.disconnect();}
    }

    private JSONObject post(String path,JSONObject value) throws Exception {
        return new JSONObject(request("POST",path,value.toString().getBytes(StandardCharsets.UTF_8),"application/json"));
    }

    private JSONObject upload(String name,byte[] image) throws Exception {
        String boundary="native-android-fixture";
        ByteArrayOutputStream body=new ByteArrayOutputStream();
        body.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+name+"\"\r\nContent-Type: image/png\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        body.write(image);body.write(("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8));
        return new JSONObject(request("POST","/api/assets",body.toByteArray(),"multipart/form-data; boundary="+boundary));
    }

    private String javascript(String script) throws Exception {
        CountDownLatch done=new CountDownLatch(1);String[] result={null};
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->activity.getActivity().getEditorWebView().evaluateJavascript(script,value->{result[0]=value;done.countDown();}));
        assertTrue("Android WebView did not respond",done.await(30,TimeUnit.SECONDS));
        return result[0];
    }

    @Test public void nativeDependenciesAndActualOfflineWebViewBoot() throws Exception {
        JSONObject dependencies=new JSONObject(Python.getInstance().getModule("android_entry").callAttr("diagnostics").toString());
        assertEquals("1.23.3",dependencies.getString("numpy"));assertEquals("1.10.26",dependencies.getString("pydantic"));
        assertTrue(dependencies.getString("opencv").startsWith("4.5.1"));assertEquals("9.2.0",dependencies.getString("pillow"));
        assertEquals(253,new JSONArray(request("GET","/api/stickers",null,null)).length());
        long deadline=System.currentTimeMillis()+60_000;
        while(!"true".equals(javascript("Boolean(document.querySelector('.mobile-tabs'))")) && System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertEquals("true",javascript("Boolean(document.querySelector('.mobile-tabs'))"));
        assertEquals("true",javascript("document.documentElement.scrollWidth<=innerWidth+1"));
        assertEquals("true",javascript("(()=>{const gl=document.createElement('canvas').getContext('webgl2');if(!gl)return false;gl.getExtension('WEBGL_lose_context')?.loseContext();return true;})()"));
    }

    private void waitFor(String expression) throws Exception {
        long deadline=System.currentTimeMillis()+60_000;
        while(!"true".equals(javascript(expression))&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertEquals("Native WebView condition: "+expression,"true",javascript(expression));
    }

    private Bitmap renderProject(JSONObject project) throws Exception {
        JSONObject current=new JSONObject(request("GET","/api/project",null,null));
        request("PUT","/api/project",new JSONObject().put("baseRevision",current.getLong("revision")).put("project",project).toString().getBytes(StandardCharsets.UTF_8),"application/json");
        String step="?native-step="+java.util.UUID.randomUUID();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->activity.getActivity().getEditorWebView().loadUrl(address+"/"+step));
        waitFor("location.search==="+JSONObject.quote(step)+"&&document.querySelector('canvas[aria-label=封面画布]')?.getAttribute('aria-busy')==='false'");
        assertEquals("0",javascript("document.querySelectorAll('.error-banner').length"));
        String data=new JSONArray("["+javascript("document.querySelector('canvas[aria-label=封面画布]').toDataURL('image/png')")+"]").getString(0);
        byte[] encoded=android.util.Base64.decode(data.substring(data.indexOf(',')+1),android.util.Base64.NO_WRAP);
        Bitmap image=BitmapFactory.decodeByteArray(encoded,0,encoded.length);
        assertNotNull(image);assertEquals(1920,image.getWidth());assertEquals(1080,image.getHeight());return image;
    }

    private long differences(Bitmap first,Bitmap second) {
        int count=first.getWidth()*first.getHeight();int[] a=new int[count],b=new int[count];
        first.getPixels(a,0,first.getWidth(),0,0,first.getWidth(),first.getHeight());
        second.getPixels(b,0,second.getWidth(),0,0,second.getWidth(),second.getHeight());
        long changed=0;for(int i=0;i<count;i++)if(a[i]!=b[i])changed++;return changed;
    }

    @Test public void actualThreeJsAndPixiChangeFullResolutionAndroidPixels() throws Exception {
        JSONObject original=new JSONObject(request("GET","/api/project",null,null)).getJSONObject("project");
        JSONObject project=new JSONObject(original.toString());project.put("activeRatio","16:9").put("filters",new JSONArray());
        JSONObject title=project.getJSONArray("titles").getJSONObject(0);
        title.put("text","ANDROID 3D").put("fontId","russo-one").put("color","#ff3366").put("glow",0).put("text3d",JSONObject.NULL);
        try {
            Bitmap plain=renderProject(project);
            title.put("text3d",new JSONObject().put("enabled",true));Bitmap three=renderProject(project);
            assertTrue("Actual three.js extrusion must change native WebView pixels",differences(plain,three)>100);
            project.put("filters",new JSONArray().put(new JSONObject().put("id",java.util.UUID.randomUUID().toString().replace("-",""))
                .put("type","GrayscaleFilter").put("enabled",true).put("targets",new JSONArray().put("title1")).put("params",new JSONObject())));
            Bitmap filtered=renderProject(project);
            assertTrue("Actual Pixi filter must change native WebView pixels",differences(three,filtered)>100);
            plain.recycle();three.recycle();filtered.recycle();
        } finally {renderProject(original).recycle();}
    }

    @Test public void actualEmbeddedChartFramePreviewsNativeGoldTrack() throws Exception {
        waitFor("Boolean(document.querySelector('.mobile-tabs'))");
        javascript("Array.from(document.querySelectorAll('button')).find(button=>button.textContent==='从谱面生成').click()");
        waitFor("Boolean(document.querySelector('input[aria-label=谱面文件]'))");
        String chart=new JSONObject().put("pathData","RRRRUULLDDRRRR")
            .put("settings",new JSONObject().put("song","Native chart").put("artist","Test").put("bpm",100))
            .put("actions",new JSONArray().put(new JSONObject().put("floor",2).put("eventType","SetSpeed").put("speedType","Bpm").put("beatsPerMinute",200))
                .put(new JSONObject().put("floor",5).put("eventType","Twirl"))).toString();
        javascript("(()=>{const input=document.querySelector('input[aria-label=谱面文件]');const transfer=new DataTransfer();transfer.items.add(new File(["+JSONObject.quote(chart)+"],'native-test.adofai',{type:'application/json'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()");
        String frame="document.querySelector('iframe[title=轨道选段工具]')?.contentDocument";
        waitFor("Boolean("+frame+"?.querySelector('#track-style'))");
        assertEquals("\"gold\"",javascript(frame+".querySelector('#track-style').value"));
        javascript("(()=>{const doc="+frame+";for(const [id,value] of [['resolution','1920'],['aspect','16:9']]){const input=doc.querySelector('#'+id);input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}doc.querySelector('#export-png').click();})()");
        waitFor("(()=>{const image=document.querySelector('img[alt=生成轨道预览]');return Boolean(image?.complete&&image.naturalWidth===1920);})()");
        String imageUrl=new JSONArray("["+javascript("document.querySelector('img[alt=生成轨道预览]').src")+"]").getString(0);
        byte[] png=binaryRequest("GET",new URL(imageUrl).getFile(),null,null);
        Bitmap image=BitmapFactory.decodeByteArray(png,0,png.length);assertNotNull(image);
        assertEquals(1920,image.getWidth());assertEquals(1080,image.getHeight());
        int[] pixels=new int[1920*1080];image.getPixels(pixels,0,1920,0,0,1920,1080);long gold=0,transparent=0;
        for(int pixel:pixels){int r=(pixel>>16)&255,g=(pixel>>8)&255,b=pixel&255,a=(pixel>>>24);if(a==0)transparent++;if(a==255&&r>170&&g>140&&b<160)gold++;}
        assertTrue("Track material must be rendered by real native Pillow",gold>1000);assertTrue(transparent>1000);image.recycle();
    }

    @Test public void javaOnnxRuntimeMatchesTheOriginalModelReference() throws Exception {
        JSONObject reference=new JSONObject(new String(asset("model-reference.json"),StandardCharsets.UTF_8));
        ByteBuffer input=ByteBuffer.allocate(3*320*320*Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        for(int i=0;i<3*320*320;i++)input.putFloat((i%251)/251f);
        String root=Python.getInstance().getModule("experiments.p0").callAttr("resource_root").toString();
        String model=new java.io.File(root,"models/u2netp.onnx").getAbsolutePath();
        String encoded=ModelInference.predict(model,android.util.Base64.encodeToString(input.array(),android.util.Base64.NO_WRAP));
        byte[] output=android.util.Base64.decode(encoded,android.util.Base64.NO_WRAP);
        assertEquals(320*320*Float.BYTES,output.length);
        var floats=ByteBuffer.wrap(output).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
        double sum=0;for(int i=0;i<floats.limit();i++){float value=floats.get(i);assertFalse(Float.isNaN(value));assertFalse(Float.isInfinite(value));sum+=value;}
        assertEquals(reference.getDouble("mean"),sum/floats.limit(),.001);
        JSONArray indices=reference.getJSONArray("indices"),expected=reference.getJSONArray("values");
        for(int i=0;i<indices.length();i++)assertEquals(expected.getDouble(i),floats.get(indices.getInt(i)),.001);
    }

    @Test public void allNineApprovedSamplesKeepTheOriginalNinetyPercentIouGate() throws Exception {
        JSONArray samples=new JSONArray(new String(asset("solid/manifest.json"),StandardCharsets.UTF_8));
        assertEquals(9,samples.length());
        for(int i=0;i<samples.length();i++) {
            JSONObject sample=samples.getJSONObject(i);
            JSONObject uploaded=upload(sample.getString("image"),asset("solid/"+sample.getString("image")));
            JSONObject job=post("/api/jobs",new JSONObject().put("source",uploaded.getString("id")));
            long deadline=System.currentTimeMillis()+40_000;
            while(job.getString("status").equals("running") && System.currentTimeMillis()<deadline) {
                Thread.sleep(50);job=new JSONObject(request("GET","/api/jobs/"+job.getString("id"),null,null));
            }
            assertEquals(sample.getString("id")+": "+job,"succeeded",job.getString("status"));
            byte[] mask=binaryRequest("GET","/api/assets/"+job.getJSONObject("result").getString("id"),null,null);
            byte[] truth=asset("solid/"+sample.getString("truth"));
            byte[] truthDigest=java.security.MessageDigest.getInstance("SHA-256").digest(truth);
            StringBuilder hex=new StringBuilder();for(byte value:truthDigest)hex.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
            assertEquals(sample.getString("truth_sha256"),hex.toString());
            Bitmap predicted=BitmapFactory.decodeByteArray(mask,0,mask.length),target=BitmapFactory.decodeByteArray(truth,0,truth.length);
            assertEquals(target.getWidth(),predicted.getWidth());assertEquals(target.getHeight(),predicted.getHeight());
            int count=target.getWidth()*target.getHeight();int[] p=new int[count],t=new int[count];
            predicted.getPixels(p,0,target.getWidth(),0,0,target.getWidth(),target.getHeight());
            target.getPixels(t,0,target.getWidth(),0,0,target.getWidth(),target.getHeight());
            long intersection=0,union=0;
            for(int j=0;j<count;j++){boolean a=((p[j]>>16)&255)>=128,b=((t[j]>>16)&255)>=128;if(a&&b)intersection++;if(a||b)union++;}
            assertTrue("Ground truth cannot be empty",union>0);
            assertTrue(sample.getString("id")+" IoU="+(double)intersection/union,(double)intersection/union>=.9);
            predicted.recycle();target.recycle();
        }
    }

    @Test public void sqliteSaveSurvivesOpeningAnotherStoreConnection() throws Exception {
        JSONObject initial=new JSONObject(request("GET","/api/project",null,null));
        JSONObject changed=new JSONObject(initial.getJSONObject("project").toString());changed.put("name","native-save-test");
        JSONObject saved=new JSONObject(request("PUT","/api/project",new JSONObject().put("baseRevision",initial.getLong("revision")).put("project",changed).toString().getBytes(StandardCharsets.UTF_8),"application/json"));
        try {
            JSONObject reloaded=new JSONObject(request("GET","/api/project",null,null));
            assertEquals("native-save-test",reloaded.getJSONObject("project").getString("name"));
            assertEquals(saved.getLong("revision"),reloaded.getLong("revision"));
        } finally {
            request("PUT","/api/project",new JSONObject().put("baseRevision",saved.getLong("revision")).put("project",initial.getJSONObject("project")).toString().getBytes(StandardCharsets.UTF_8),"application/json");
        }
    }
}
