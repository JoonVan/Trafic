import time
import os.path
import tensorflow as tf
import numpy as np
import networkDef as nn
import argparse
import sys
from fiberfileIO import *
from datetime import datetime
import shutil
import json

YELLOW = "\033[0;33m"
NC = "\033[0m"
flags = tf.app.flags
FLAGS = flags.FLAGS
flags.DEFINE_float('learning_rate', 0.000001, 'Initial learning rate.')
flags.DEFINE_integer('number_epochs', 3, 'Number of epochs to run trainer.')
flags.DEFINE_integer('number_hidden', 1024, 'Size of hidden layers. Not currently in use')
flags.DEFINE_integer('number_layers', 3, 'Number of layers. Not currently in use')
flags.DEFINE_integer('batch_size', 5, 'Batch size.')
flags.DEFINE_string('input_dir', '',
                    'Directory with the training data.')
flags.DEFINE_string('checkpoint_dir', '',
                    """Directory where to write model checkpoints.""")
flags.DEFINE_string('summary', '',
                    """Directory where to write summary.""")

def run_training(input_dir, checkpoint_dir, summary, number_epochs=3, learning_rate=0.000001, batch_size=5, number_hidden=1024, number_layers=3):
    
    num_classes = 0

    checkpoint_dir = os.path.join(checkpoint_dir,datetime.now().strftime("%Y%m%d-%H%M%S"))
    if not os.path.isdir(checkpoint_dir):
        os.makedirs(checkpoint_dir)

    shutil.copy(os.path.join(input_dir, 'dataset_description.json'), os.path.join(checkpoint_dir, 'dataset_description.json'))

    description_dict = {}
    ## output json description file
    with open(os.path.join(checkpoint_dir, 'dataset_description.json'), 'r') as json_desc_file:
        json_string = json_desc_file.read()
        description_dict = json.loads(json_string)
        num_classes = len(description_dict['labels'])
        store_params = description_dict['store_parameters']
        num_landmarks = store_params['num_landmarks']
        num_points = store_params['num_points']
        lmOn = store_params['lmOn']
        curvOn = store_params['curvOn']
        torsOn = store_params['torsOn']
        num_features = num_landmarks * int(lmOn) + int(curvOn) + int(torsOn)
    with open(os.path.join(checkpoint_dir, 'dataset_description.json'), 'w') as json_desc_file:
        training_parameters = {'nb_layers' : number_layers, 'batch_size' : batch_size, 'num_epochs' : number_epochs, 'num_hidden' : number_hidden, 'input_dataset' : input_dir, 'checkpoint_directory' : checkpoint_dir, 'log_directory' : summary}
        description_dict['training_parameters'] = training_parameters
        json_desc_file.write(json.dumps(description_dict, sort_keys=True, indent=4, separators=(',', ': ')))

    # with open(os.path.join(checkpoint_dir, 'dataset_description.json'), 'w') as json_desc_file:


    # construct the graph
    with tf.Graph().as_default():

        ## Output json configuration to tensorboard
        string_tensor = tf.constant(json.dumps(description_dict, sort_keys=True, indent=4, separators=(',', ': ')).replace('\n', '  \n').replace('    ', '&nbsp;&nbsp;&nbsp;&nbsp;'))
        tf.summary.text('parameters', string_tensor)

        # Define inputs
        fibers, labels = nn.inputs(input_dir, batch_size=batch_size, num_epochs=number_epochs, conv=False)
        labels = tf.reshape(labels, [-1])
        
        # Define the network
        results = nn.inference(fibers, number_hidden, num_classes, is_training=True, num_layers=number_layers)

        # Define metrics
        loss = nn.loss(results, labels)
        accuracy = nn.accuracy(results, labels)

        # Setup the training operations
        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
            train_op = nn.training(loss, learning_rate)

        # setup the summary ops to use TensorBoard
        summary_op = tf.summary.merge_all()

        # init to setup the initial values of the weights
        init_op = tf.group(tf.global_variables_initializer(),
                           tf.local_variables_initializer())

        # setup a saver for saving checkpoints
        saver = tf.train.Saver()

        # create the session
        sess = tf.Session()

        # specify where to write the log files for import to TensorBoard
        summary_writer = tf.summary.FileWriter(os.path.join(summary,datetime.now().strftime("%Y%m%d-%H%M%S")),
                                                graph=sess.graph)

        # initialize the graph
        sess.run(init_op)

        # setup the coordinato and threadsr.  Used for multiple threads to read data.
        # Not strictly required since we don't have a lot of data but typically
        # using multiple threads to read data improves performance
        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(sess=sess, coord=coord)

        # loop will continue until we run out of input training cases
        try:
            step = 0
            while not coord.should_stop():

                # start time and run one training iteration
                start_time = time.time()
                _, loss_value, accuracy_value = sess.run([train_op, loss, accuracy])
                duration = time.time() - start_time

                if step % 50 == 0:
                    print('Step %d: loss = %.12f, acc = %.10f (%.3f sec)' % (step, loss_value, accuracy_value, duration))

                    print("")

                    sys.stdout.flush()

                    # output some data to the log files for tensorboard
                    summary_str = sess.run(summary_op)
                    summary_writer.add_summary(summary_str, step)
                    summary_writer.flush()

                # less frequently output checkpoint files.  Used for evaluating the model
                if step % 1000 == 0:
                    checkpoint_path = os.path.join(checkpoint_dir,
                                                   'model.ckpt')
                    saver.save(sess, checkpoint_path, global_step=step)
                  
                step += 1

                # quit after we run out of input files to read
        except tf.errors.OutOfRangeError:
            print('Done training for %d epochs, %d steps.' % (number_epochs,
                                                              step))
            checkpoint_path = os.path.join(checkpoint_dir,
                                           'model.ckpt')
            saver.save(sess, checkpoint_path, global_step=step)

        finally:
            coord.request_stop()

        # shut down the threads gracefully
        coord.join(threads)
        sess.close()


def main(_):
    start = time.time()
    run_training(FLAGS.input_dir, FLAGS.checkpoint_dir, FLAGS.summary, FLAGS.number_epochs, FLAGS.learning_rate, FLAGS.batch_size, FLAGS.number_hidden, FLAGS.number_layers)
    end = time.time()
    print("Training Process took %dh%02dm%02ds" % (convert_time(end - start)))


if __name__ == '__main__':
    tf.app.run()
