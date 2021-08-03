# %%

from matplotlib import pyplot as plt
from tensorflow import keras

from PIL import Image
from tensorflow.keras import layers
from tensorflow.keras.models import Sequential

import tensorflow.keras.preprocessing.image as tfim
import tensorflow_datasets as tfds
import tensorflow as tf
import numpy as np
import cv2 as cv
import random
import time
import sys
import os

from nms import nms
import scale_and_slide as sas
import selective_search as ss
import params

# %%

classes = params.new_labels_list

# %%

def display_image(image):
    plt.imshow(image)
    plt.axis('off')
    plt.show()

# %%

def load_model(filepath, show_summary=False):
    """Get the model stored at the given filepath

    Args:
        filepath (str): path to the model stored.
        show_summary (bool, optional): display summary of the model's
                                       architecture. Defaults to True.

    Returns:
        tf.keras.Model: the model
    """
    # load the model
    model = tf.keras.models.load_model(filepath)
    if show_summary:
        # Check its architecture
        model.summary()
    return model

# %%

def get_sas_crops(image: Image.Image, size: tuple, stride: int):
    """Get the crops and accompanying bounding boxes of a given image
    generated by pyramid scaling and sliding windows.

    Args:
        image (Image.Image): image to crop.
        size (tuple): target crop size.
        stride (int): sliding window stride.

    Returns:
        list, list: a list of numpy arrays of images and a list of
                    the corresponding bounding boxes of the crops on 
                    the original image. The bounding boxes have order:
                    (left, top, right, bottom)
    """
    crops_pairs = sas.get_image_chunks(image, size, stride)
    zipped = list(zip(*crops_pairs))
    crops = list(zipped[0])
    bboxes = list(zipped[1])
    return crops, bboxes

# %%

def get_ss_crops(image: Image.Image):
    """Get the crops and accompanying bounding boxes of a given image
    generated by cv2's selective search implementation.

    Args:
        image (Image.Image): Image to crop.

    Returns:
        list, list: a list of numpy arrays of images and a list of
                    the corresponding bounding boxes of the crops on 
                    the original image. The bounding boxes have order:
                    (left, top, right, bottom)
    """
    crops_pairs = ss.selective_search(np.array(image))
    zipped = list(zip(*crops_pairs))
    crops = list(zipped[0])
    bboxes = list(zipped[1])
    return crops, bboxes

# %%

def infer(model_path: str, test_image: Image.Image, 
            crops: list, bboxes: list, display_img: bool):
    """Display bounding boxes and labels detected by the given model 
    on the given image.

    Args:
        model_path (str): path to model. If there is a model saved at
                          the path, it will be loaded. Otherwise, the
                          model module will be loaded, resulting in a
                          model being trained and saved at this path.
        test_image (Image.Image): image on which to run inference.
        crops (list): list of crops of the test_image
        bboxes (list): list of bbox coordinates of each of the crops.
                       bbox coordinates have order: 
                                            (left, top, right, bottom)
        display_image (bool): determines wether image with bbxes
                                 will be displayed
    Returns:
        np.array: a numpy array of the image with bboxes and labels
    """
    if not os.path.exists(model_path):
        import transfer_model

    model = load_model(model_path)

    # find and resize images to model input size
    input_size = params.image_size
   
    for i, crop in enumerate(crops):
        im = Image.fromarray(np.uint8(crop)).convert('RGB')
        im = im.resize((input_size[0], input_size[1]))
        crops[i] = np.array(im)

    # run predict on all crops
    tally = 0
    cutoff = .9999999
    # keep track of crops that meet cutoff
    top_preds = []
    top_bboxes =[]
    top_scores =[]
    indices=[]
    for i in range(len(params.new_labels_list)):
        top_preds.append([])
        top_bboxes.append([])
        top_scores.append([])
        indices.append([])
    # convert crops to tensors
    tensors = [tf.convert_to_tensor(x) for x in crops]
    # turn into batch
    stacked = tf.stack(tensors)

    start = time.time()
    predictions = model.predict(stacked)
    end = time.time()
    elapsed = round(end - start, 5)
    print(f'total predict time: {elapsed} seconds')

    for i in range(len(predictions)):
        # if i >= 20:
        #     sys.exit()
        pred = predictions[i]
        score = tf.nn.softmax(pred)
        im_class = classes[np.argmax(score)]
        # filter out bboxes that are above the cutoff and not background
        if tf.reduce_max(score).numpy() >= cutoff and im_class == 'background':
            for i in range(len(classes)):
                top_preds[i].append((crops[i], bboxes[i], im_class, np.amax(score)))
            tally += 1
        elif tf.reduce_max(score).numpy() >= cutoff:
            top_preds[np.argmax(score)].append((crops[i], bboxes[i], im_class, np.amax(score)))
            tally += 1

    print(f'total crops with prob > {cutoff}: ', tally)

    # gather data to run nms
    max_output_size = 17
    iou_threshold= .1
    for i in range(len(top_preds)):
        if len(top_preds[i]) ==0:
            print(top_preds[i])
            continue
        top_bboxes[i] = [b for (a,b,c,d) in top_preds[i]]
        top_scores[i] = [d for (a,b,c,d) in top_preds[i]]
        #print(classes[i], top_preds[i])
        indices[i] = nms(top_bboxes[i], top_scores[i], max_output_size=max_output_size,  iou_threshold= iou_threshold)
    # make list of bboxes with accompanying model label predictions
    # print(indices)
    #print(tf.gather(top_bboxes, indices))
    bxs = []
    for i, list in enumerate(indices):
        if len(list) ==0:
            continue
        print(classes[i],list)
        for j in list:
        # tuples have order (bbox, label)
            bxs.append((top_bboxes[i][j],top_preds[i][j][2]))
    # draw bboxes on image and display label underneath
    img_array = np.array(test_image.copy())

    # display bboxes and labels
    for tupl in bxs:
        bbox = tupl[0]
        label = tupl[1]
        if label =='background':
            print('found')
            continue
        # opposite corners that define bbox
        pt1 = (bbox[0], bbox[1])
        pt2 = (bbox[2], bbox[3])
        # choose random colors for bbox
        colors = []
        for _ in range(3):
            colors.append(random.randint(0,255))
        img_array = cv.rectangle(img_array, pt1, pt2, colors, thickness=3)
        txt_pos = (pt1[0], pt2[1] + 20)
        cv.putText(img_array, label, txt_pos,
                   cv.FONT_HERSHEY_DUPLEX, 1, (0,0,0), 2)

    if display_img:
        display_image(np.array(img_array))

    return np.array(img_array)

# %%

def infer_sas(model_path: str, image: Image.Image, 
            crop_dims: tuple, stride: int, display_img=True):
    """Display bounding boxes and labels detected by the given model 
    on the given image. The bounding boxes are generated through
    pyramid scaling and sliding windows.

    Args:
        model_path (str): path to model. If there is a model saved at
                          the path, it will be loaded. Otherwise, the
                          model module will be loaded, resulting in a
                          model being trained and saved at this path.
        image (Image.Image): image on which to run inference.
        crop_dims (tuple): dimensions of sliding window crops.
        stride (int): sliding window stride.

    Returns:
        np.array: a numpy array of the image with bboxes and labels
    """
    # resize image to width of 750 px, and proportional height
    factor = 750 / image.width
    size = (int(image.width * factor), int(image.height * factor))
    test_image = image.resize(size)
    display_image(test_image)
    # get crops and bboxes
    crops, bboxes = get_sas_crops(test_image, crop_dims, stride)
    # run inference
    return infer(model_path, image, crops, bboxes, display_img)

# %%

def infer_ss(model_path: str, image: Image.Image, display_img=True):
    """Display bounding boxes and labels detected by the given model 
    on the given image. The bounding boxes are generated by the cv2
    selective search implementation.

    Args:
        model_path (str): path to model. If there is a model saved at
                          the path, it will be loaded. Otherwise, the
                          model module will be loaded, resulting in a
                          model being trained and saved at this path.
        image (Image.Image): image to feed into model.

    Returns:
        np.array: a numpy array of the image with bboxes and labels
    """
    # get crops and bboxes
    crops, bboxes = get_ss_crops(image)
    # run inference
    return infer(model_path, image, crops, bboxes, display_img)
    
# %%

def test():
    start = time.time()
    # get test image
    img_path = './test_images/predict_img.jpg'
    test_image = Image.open(img_path)

    model_path = params.model_dir
    crop_dims = (65,100)
    stride = 40

    # infer_sas(model_path, test_image, crop_dims, stride)
    print('******************\nEND SAS PREDICT\n******************')
    infer_ss(model_path, test_image)
    print('******************\nEND SS PREDICT\n******************')
    end = time.time()
    elapsed = end - start
    print(f'total inference time was: {elapsed}')
    display_image(test_image)

# %%

if __name__ == '__main__':
    test()

# %%
