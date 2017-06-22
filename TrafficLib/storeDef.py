import sys
from fiberfileIO import *
import numpy as np
import os
import tensorflow as tf


class data_set:
    def __init__(self, height, rows, cols):
        self.data = np.ndarray(shape=(height, rows, cols))
        self.labels = np.ndarray(shape=height)

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def convert_to(data_set, name, directory):
    """Converts a dataset to tfrecords."""
    fibers = data_set.data
    labels = data_set.labels

    num_fib = fibers.shape[0]

    if labels.shape[0] != num_fib:
        raise ValueError('size %d does not match label size %d.' %
                         (fibers.shape[0], num_fib))
    rows = fibers.shape[1]
    cols = fibers.shape[2]

    filename = os.path.join(directory, name + '.tfrecords')
    print 'Writing', filename
    writer = tf.python_io.TFRecordWriter(filename)
    for index in range(num_fib):
        # print "Label:", labels[index].dtype
        fiber_raw = fibers[index].tostring()
        example = tf.train.Example(features=tf.train.Features(feature={
            'num_features': _int64_feature(rows),
            'num_points': _int64_feature(cols),
            'label': _bytes_feature(labels[index].tostring()),
            'fiber_raw': _bytes_feature(fiber_raw)}))
        writer.write(example.SerializeToString())
    writer.close()


def fiber_extract_feature(fiber_file, lmOn, curveOn, torsOn, num_landmarks, num_points, label, train=False):
    array_name = []
    dataset = []
    labels = []

    fiber = read_vtk_data(fiber_file)
    nb_fibers = fiber.GetNumberOfCells()
    nb_features = 0
    if lmOn:
        nb_features += num_landmarks
        for i in range(0, num_landmarks):
            array_name.append("Distance2Landmark" + str(i+1))
    if curveOn:
        nb_features += 1
        array_name.append("curvature")
    if torsOn:
        nb_features += 1
        array_name.append("torsion")

    for k in range(0, nb_fibers):
        fiber_data = np.ndarray(shape=(nb_features, num_points), dtype=np.float64)
        for i in range(0, nb_features):
            feature_array = fiber.GetPointData().GetScalars(array_name[i])
            for j in range(k*num_points, (k+1)*num_points):
                fiber_data[i, j % num_points] = feature_array.GetTuple1(j)

        # Find a better normalization
        # max_value = np.amax(fiber_data, 1)
        # min_value = np.amin(fiber_data, 1)
        # for l in range(0, nb_features):
        #     fiber_data[l, :] = (fiber_data[l, :] - (max_value[l] + min_value[l]) / 2) / \
        #                        (max_value[l] - min_value[l])
        if fiber_data.shape != (nb_features, num_points):
            raise Exception('Unexpected image shape: %s' % str(fiber_data.shape))
        dataset.append(fiber_data)

        if train:   # If it's a training
            labels.append(label)
        else:   # If it's a testing
            labels.append(label+":"+str(k))

    return dataset, labels