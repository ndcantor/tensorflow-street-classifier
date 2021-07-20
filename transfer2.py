# %%
import matplotlib.pyplot as plt
import numpy as np
import os
import tensorflow as tf
from tensorflow.keras import preprocessing
from tensorflow.keras.preprocessing import image_dataset_from_directory
from params import image_size, label_list, model_dir
import load_data
# %%
load_data.main()
# %%
class_number = len(label_list) # for background
IMG_SIZE = image_size[:2]
BATCH_SIZE = 32
# %%
model = tf.keras.applications.ResNet50(weights='imagenet')
# %%
base_model = tf.keras.applications.ResNet50(weights='imagenet',include_top=False)
# %%
x = base_model.output
x = tf.keras.layers.GlobalAveragePooling2D()(x)
# %%
x = tf.keras.layers.Dense(1024, activation='relu')(x)
x = tf.keras.layers.Dense(1024, activation='relu')(x)
x = tf.keras.layers.Dense(1024, activation='relu')(x)
x = tf.keras.layers.Dense(512, activation='relu')(x)
preds = tf.keras.layers.Dense(class_number, activation ='softmax')(x)
# %%
model = tf.keras.models.Model(inputs=base_model.input, outputs=preds)
# %%
"""
making the first 140 layers untrainable and the last ones trainable
"""
braek = 140
for layer in model.layers[:braek]:
    layer.trainable = False
for layer in model.layers[braek:]:
    layer.trainable = True
# %%
train_datagen = tf.keras.preprocessing.image.ImageDataGenerator(preprocessing_function=tf.keras.applications.resnet50.preprocess_input)
# %%
train_generator = train_datagen.flow_from_directory(
    './data/train', 
    target_size = (224, 224),
    color_mode = 'rgb',
    batch_size = 32,
    class_mode = 'categorical',
    shuffle = True
)
# %%
print(model.summary())
# %%
model.compile(
    optimizer='Adam', 
    loss='categorical_crossentropy', 
    metrics=['accuracy']
)
# %%
epochs = 15
history = model.fit_generator(generator = train_generator, steps_per_epoch=train_generator.n//train_generator.batch_size, epochs = epochs)
# %%
model.save(model_dir)
# %%
import confusionMatrix
# %%