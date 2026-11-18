"""Run the bundled fallback model through the official Android ONNX runtime."""
import base64
import numpy as np


def predict(tensor, model):
    from java import jclass
    bridge = jclass('com.zac688.adofaicoverstudio.ModelInference')
    encoded = base64.b64encode(tensor.astype('<f4', copy=False).tobytes()).decode('ascii')
    output = bridge.predict(str(model), encoded)
    return np.frombuffer(base64.b64decode(str(output)), dtype='<f4').reshape((320, 320)).copy()
