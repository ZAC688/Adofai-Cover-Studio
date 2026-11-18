package com.zac688.adofaicoverstudio;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import android.util.Base64;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.Collections;

public final class ModelInference {
    private ModelInference() {}

    public static String predict(String model, String input) throws Exception {
        byte[] bytes = Base64.decode(input, Base64.NO_WRAP);
        if (bytes.length != 3 * 320 * 320 * Float.BYTES) {
            throw new IllegalArgumentException("Invalid model input dimensions");
        }
        OrtEnvironment environment = OrtEnvironment.getEnvironment();
        try (OrtSession.SessionOptions options = new OrtSession.SessionOptions()) {
            options.setIntraOpNumThreads(2);
            try (OrtSession session = environment.createSession(model, options);
                 OnnxTensor tensor = OnnxTensor.createTensor(environment,
                     ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer(),
                     new long[]{1, 3, 320, 320});
                 OrtSession.Result result = session.run(Collections.singletonMap(
                     session.getInputNames().iterator().next(), tensor))) {
                OnnxTensor output = (OnnxTensor) result.get(0);
                FloatBuffer values = output.getFloatBuffer();
                if (values.remaining() != 320 * 320) {
                    throw new IllegalStateException("Invalid model output dimensions");
                }
                ByteBuffer buffer = ByteBuffer.allocate(320 * 320 * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
                buffer.asFloatBuffer().put(values);
                return Base64.encodeToString(buffer.array(), Base64.NO_WRAP);
            }
        }
    }
}
