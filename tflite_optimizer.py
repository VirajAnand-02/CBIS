import tensorflow as tf

# Load the saved Keras model
saved_model = tf.keras.models.load_model("image_attribute_router.h5")

# Convert the model to TFLite format
converter = tf.lite.TFLiteConverter.from_keras_model(saved_model)

# Apply optimizations (e.g., quantize weights to 16-bit floats)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.float16]

tflite_model = converter.convert()

# Save the TFLite model
with open("image_router.tflite", "wb") as f:
    f.write(tflite_model)

print("TFLite model saved as image_router.tflite")