import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Input
from tensorflow.keras.applications import MobileNetV3Small
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
import pandas as pd

# --- GPU Configuration ---
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print(f"GPUs detected and memory growth enabled: {gpus}")
    except RuntimeError as e:
        print(e)

# --- 1. Configuration ---
# Set a high number of epochs; EarlyStopping will find the optimal number.
EPOCHS = 100 
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
IMAGE_DIR = './img'
CSV_PATH = './img/labels.csv'
MODEL_SAVE_PATH = "image_attribute_router.keras"

# The order MUST match the columns in your CSV file (after the filename column)
from dataset_DL.cfg_file import ATTRIBUTES
NUM_ATTRIBUTES = len(ATTRIBUTES)

# --- 2. Load Data ---
print("Loading data...")
df = pd.read_csv(CSV_PATH)

# Generator for training data: USES data augmentation
train_datagen = ImageDataGenerator(
    rescale=1./255.,
    validation_split=0.2, # This is still needed to split the dataframe
    rotation_range=20,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest'
)

# Generator for validation data: DOES NOT use data augmentation (only rescaling)
validation_datagen = ImageDataGenerator(
    rescale=1./255.,
    validation_split=0.2 # This correctly selects the same validation split as above
)

train_generator = train_datagen.flow_from_dataframe(
    dataframe=df,
    directory=IMAGE_DIR,
    x_col='image_filename',
    y_col=ATTRIBUTES,
    subset="training",
    batch_size=BATCH_SIZE,
    seed=42,
    shuffle=True,
    class_mode="raw",
    target_size=IMG_SIZE
)

validation_generator = validation_datagen.flow_from_dataframe(
    dataframe=df,
    directory=IMAGE_DIR,
    x_col='image_filename',
    y_col=ATTRIBUTES,
    subset="validation",
    batch_size=BATCH_SIZE,
    seed=42,
    shuffle=False, # No need to shuffle validation data
    class_mode="raw",
    target_size=IMG_SIZE
)

# --- 3. Build the Model ---
print("Building model...")
base_model = MobileNetV3Small(
    input_shape=IMG_SIZE + (3,),
    include_top=False,
    weights='imagenet'
)
base_model.trainable = False

inputs = Input(shape=IMG_SIZE + (3,))
x = base_model(inputs, training=False) # Important: run base model in inference mode
x = GlobalAveragePooling2D()(x)
outputs = Dense(NUM_ATTRIBUTES, activation='sigmoid', name='attributes')(x)
model = Model(inputs, outputs)

# --- 4. Compile and Train ---
print("Compiling model...")
model.compile(
    optimizer=Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=[
        tf.keras.metrics.BinaryAccuracy(name='accuracy'), # Better for multi-label
        tf.keras.metrics.AUC(name='auc', multi_label=True) # Excellent for this task
    ]
)
model.summary()

# Callbacks for robust training
# Save the best model based on validation AUC
model_checkpoint = ModelCheckpoint(
    filepath=MODEL_SAVE_PATH,
    monitor='val_auc', # Monitor validation Area Under Curve
    mode='max',          # We want to maximize AUC
    save_best_only=True,
    verbose=1
)

# Stop training if validation AUC doesn't improve for 10 epochs
early_stopping = EarlyStopping(
    monitor='val_auc',
    mode='max',
    patience=10, # Number of epochs to wait for improvement
    restore_best_weights=True, # Restores model weights from the epoch with the best value
    verbose=1
)

print("Training model...")
history = model.fit(
    train_generator,
    validation_data=validation_generator,
    epochs=EPOCHS,
    callbacks=[model_checkpoint, early_stopping]
)

# --- 5. Save the Final Model ---
# Note: The Callbacks already saved the best version of the model.
# We will now load that best model and attach the attribute list for portability.
print("Loading best saved model...")
final_model = tf.keras.models.load_model(MODEL_SAVE_PATH)

# Attach the attribute list to the model's config for easy use in inference
final_model.config.attributes = ATTRIBUTES

# Re-save the model, now with the attributes metadata included
print(f"Saving final model with metadata to {MODEL_SAVE_PATH}...")
final_model.save(MODEL_SAVE_PATH)

print("Training and saving complete.")