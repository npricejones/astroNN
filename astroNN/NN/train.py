# ---------------------------------------------------------#
#   astroNN.NN.train: train models
# ---------------------------------------------------------#

import datetime
import os
from functools import reduce

import astroNN.NN.cnn_models
import astroNN.NN.cnn_visualization
import astroNN.NN.test
import astroNN.NN.train_tools
import h5py
import numpy as np
import tensorflow as tf
from keras.backend import set_session
from keras.callbacks import EarlyStopping, ReduceLROnPlateau, CSVLogger
from keras.optimizers import Adam
from keras.utils import plot_model


def apogee_train(h5name=None, target=None, test=True, model=None, num_hidden=None, num_filters=None, check_cannon=False,
                 activation=None, initializer=None, filter_length=None, pool_length=None, batch_size=None,
                 max_epochs=None, lr=None, early_stopping_min_delta=None, early_stopping_patience=None,
                 reuce_lr_epsilon=None, reduce_lr_patience=None, reduce_lr_min=None, cnn_visualization=True,
                 cnn_vis_num=None, test_noisy=None):
    """
    NAME: apogee_train
    PURPOSE: To train
    INPUT:
        h5name: name of h5 data, {h5name}_train.h5   {h5name}_test.h5
        target name (list):
                teff
                logg
                M
                alpha
                C
                Cl
                N
                O
                Na
                Mg
                Al
                Si
                P
                S
                K
                Ca
                Ti
                Ti2
                V
                Cr
                Mn
                Fe
                Ni
                all <- Means all of above
        test (boolean): whether test data or not after training
        model: which model defined in astroNN.NN.cnn_model.py
        num_hidden = [] number of nodes in each of the hidden fully connected layers
        num_filters = [] number of filters used in the convolutional layers
        activation = activation function used every layer except for the output layers (https://keras.io/activations/)
        initializer = model weight initializer
        filter_length = length of the filters in the convolutional layers
        pool_length = length of the maxpooling window
        batch_size = number of spectra fed into model at once during training
        max_epochs = maximum number of interations for model training
        lr = initial learning rate for optimization algorithm
        early_stopping_min_delta
        early_stopping_patience
        reduce_lr_patience
        reduce_lr_min
        check_cannon: True to check how Cannon performed on the same dataset, !!Only has effect if and only if
        test=True!!
        cnn_visualization: whether do cnn visualization or not after training
        cnn_vis_num: number of spectra for cnn visualization!!Only has effect if and only if cnn_visualization=True!!
        test_noisy: whether of not test [train + noise + translation] data
    OUTPUT: model
    HISTORY:
        2017-Oct-14 Henry Leung
    """
    beta_1 = 0.9  # exponential decay rate for the 1st moment estimates for optimization algorithm
    beta_2 = 0.999  # exponential decay rate for the 2nd moment estimates for optimization algorithm
    optimizer_epsilon = 1e-08  # a small constant for numerical stability for optimization algorithm

    if h5name is None:
        raise ValueError('Please specift the dataset name using h5name="...... "')
    if target is None:
        raise ValueError('Please specift a list of target names using target=[.., ...], target must be a list')
    if model is None:
        model = 'cnn_apogee_1'
        print('No predefined model specified, using cnn_apogee_1 as default')
    if num_hidden is None:
        raise ValueError('Please specift a list of number of neurons using num_hidden=[.., ...], must be a list')
    if activation is None:
        activation = 'relu'
        print('activation not provided, using default activation={}'.format(activation))
    if initializer is None:
        initializer = 'he_normal'
        print('initializer not provided, using default initializer={}'.format(initializer))
    if filter_length is None:
        filter_length = 8
        print('filter_length not provided, using default filter_length={}'.format(filter_length))
    if pool_length is None:
        pool_length = 4
        print('pool_length not provided, using default pool_length={}'.format(pool_length))
    if batch_size is None:
        batch_size = 64
        print('pool_length not provided, using default batch_size={}'.format(batch_size))
    if max_epochs is None:
        max_epochs = 200
        print('max_epochs not provided, using default max_epochs={}'.format(max_epochs))
    if lr is None:
        lr = 1e-5
        print('lr [Learning rate] not provided, using default lr={}'.format(lr))
    if early_stopping_min_delta is None:
        early_stopping_min_delta = 5e-6
        print('early_stopping_min_delta not provided, using default early_stopping_min_delta={}'.format(lr))
    if early_stopping_patience is None:
        early_stopping_patience = 8
        print('early_stopping_patience not provided, using default early_stopping_patience={}'.format(lr))
    if reuce_lr_epsilon is None:
        reuce_lr_epsilon = 7e-3
        print('reuce_lr_epsilon not provided, using default reuce_lr_epsilon={}'.format(lr))
    if reduce_lr_patience is None:
        reduce_lr_patience = 2
        print('reduce_lr_patience not provided, using default reduce_lr_patience={}'.format(lr))
    if reduce_lr_min is None:
        reduce_lr_min = 7e-08
        print('reduce_lr_min not provided, using default reduce_lr_min={}'.format(lr))

    now = datetime.datetime.now()
    runno = 1
    for runno in range(1, 99999):
        folder_name = 'apogee_train_{}{:02d}_run{:03d}'.format(now.month, now.day, runno)
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            break
        else:
            runno += 1

    currentdir = os.getcwd()
    fullfilepath = os.path.join(currentdir, folder_name + '/')

    with open(fullfilepath + 'hyperparameter_{}{:02d}_run{}.txt'.format(now.month, now.day, runno), 'w') as h:
        h.write("model: {} \n".format(model))
        h.write("num_hidden: {} \n".format(num_hidden))
        h.write("num_filters: {} \n".format(num_filters))
        h.write("activation: {} \n".format(activation))
        h.write("initializer: {} \n".format(initializer))
        h.write("filter_length: {} \n".format(filter_length))
        h.write("pool_length: {} \n".format(pool_length))
        h.write("batch_size: {} \n".format(batch_size))
        h.write("max_epochs: {} \n".format(max_epochs))
        h.write("lr: {} \n".format(lr))
        h.write("early_stopping_min_delta: {} \n".format(early_stopping_min_delta))
        h.write("early_stopping_patience: {} \n".format(early_stopping_patience))
        h.write("reuce_lr_epsilon: {} \n".format(reuce_lr_epsilon))
        h.write("reduce_lr_min: {} \n".format(reduce_lr_min))
        h.close()

    if target == ['all']:
        target = ['teff', 'logg', 'M', 'alpha', 'C', 'Cl', 'N', 'O', 'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Ca', 'Ti',
                  'Ti2', 'V', 'Cr', 'Mn', 'Fe', 'Ni']

    target = np.asarray(target)
    h5data = h5name + '_train.h5'

    with h5py.File(h5data) as F:  # ensure the file will be cleaned up
        i = 0
        index_not9999 = []
        for tg in target:
            temp = np.array(F['{}'.format(tg)])
            temp_index = np.where(temp != -9999)
            if i == 0:
                index_not9999 = temp_index
                i += 1
            else:
                index_not9999 = reduce(np.intersect1d, (index_not9999, temp_index))

        spectra = np.array(F['spectra'])
        spectra = spectra[index_not9999]
        # specpix_std = np.std(spectra)

        # Dont do std, so equal 1 deliberately
        specpix_std = 1
        specpix_mean = np.median(spectra)
        spectra -= specpix_mean
        spectra /= specpix_std
        num_flux = spectra.shape[1]
        num_train = int(0.8 * spectra.shape[0])  # number of training example, rest are cross validation
        num_cv = spectra.shape[0] - num_train  # cross validation
        # load data
        mean_labels = np.array([])
        std_labels = np.array([])

        i = 0
        y = np.array((spectra.shape[1]))
        for tg in target:
            temp = np.array(F['{}'.format(tg)])
            temp = temp[index_not9999]
            if i == 0:
                y = temp[:]
                i += 1
            else:
                y = np.column_stack((y, temp[:]))
            mean_labels = np.append(mean_labels, np.mean(temp))
            std_labels = np.append(std_labels, np.std(temp))
        F.close()

    print('Each spectrum contains ' + str(num_flux) + ' wavelength bins')
    print('Training set includes ' + str(num_train) + ' spectra and the cross-validation set includes ' + str(num_cv)
          + ' spectra')

    mu_std = np.vstack((mean_labels, std_labels))
    spec_meanstd = np.vstack((specpix_mean, specpix_std))
    num_labels = mu_std.shape[1]

    # prevent Tensorflow taking up all the GPU memory
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    set_session(tf.Session(config=config))

    input_shape = (None, num_flux, 1)  # shape of input spectra that is fed into the input layer

    # model selection according to user-choice
    model = getattr(astroNN.NN.cnn_models, model)(input_shape, initializer, activation, num_filters, filter_length,
                                                  pool_length, num_hidden, num_labels)

    loss_function = 'mean_squared_error'

    # compute accuracy and mean absolute deviation
    metrics = ['mae']

    csv_logger = CSVLogger(fullfilepath + 'log.csv', append=True, separator=',')

    optimizer = Adam(lr=lr, beta_1=beta_1, beta_2=beta_2, epsilon=optimizer_epsilon, decay=0.0)

    early_stopping = EarlyStopping(monitor='val_loss', min_delta=early_stopping_min_delta,
                                   patience=early_stopping_patience, verbose=2, mode='min')

    reduce_lr = ReduceLROnPlateau(monitor='loss', factor=0.5, epsilon=reuce_lr_epsilon,
                                  patience=reduce_lr_patience, min_lr=reduce_lr_min, mode='min', verbose=2)

    model.compile(optimizer=optimizer, loss=loss_function, metrics=metrics)

    model.fit_generator(astroNN.NN.train_tools.generate_train_batch(num_train, batch_size, 0, mu_std, spectra, y),
                        steps_per_epoch=num_train / batch_size,
                        epochs=max_epochs,
                        validation_data=astroNN.NN.train_tools.generate_cv_batch(num_cv, batch_size, num_train, mu_std,
                                                                                 spectra, y),
                        max_queue_size=10, verbose=2, callbacks=[early_stopping, reduce_lr, csv_logger],
                        validation_steps=num_cv / batch_size)

    astronn_model = 'model_{}{:02d}_run{:03d}.h5'.format(now.month, now.day, runno)
    model.save(fullfilepath + astronn_model)
    print(astronn_model + ' saved to {}'.format(fullfilepath))
    np.save(fullfilepath + 'meanstd.npy', mu_std)
    np.save(fullfilepath + 'spectra_meanstd.npy', spec_meanstd)
    np.save(fullfilepath + 'targetname.npy', target)
    plot_model(model, show_shapes=True,
               to_file=fullfilepath + 'apogee_train_{}{:02d}_run{}.png'.format(now.month, now.day, runno))

    # visalize cnn filter
    if cnn_visualization is True:
        print('\n')
        print('Running astroNN.NN.cnn_visualization.cnn_visualization(), it may takes a while')
        astroNN.NN.cnn_visualization.cnn_visualization(h5name=h5name, folder_name=folder_name, num=cnn_vis_num)
        print('Finished, cnn visualization')

    # Test after training
    if test is True:
        print('\n')
        print('Running astroNN.NN.test.apogee_model_eval(), it may takes a while')
        astroNN.NN.test.apogee_model_eval(folder_name=folder_name, h5name=h5name, check_cannon=check_cannon,
                                          test_noisy=test_noisy)
        print('Finished plotting')
        print('\n')
    print('Finish running apogee_train()')

    return model


def gaia_train(h5name=None, test=True, model=None, num_hidden=None, num_filters=None,activation=None, initializer=None,
               filter_length=None, pool_length=None, batch_size=None, max_epochs=None, lr=None,
               early_stopping_min_delta=None, early_stopping_patience=None,reuce_lr_epsilon=None,
               reduce_lr_patience=None, reduce_lr_min=None, cnn_visualization=True, cnn_vis_num=None):
    """
    NAME: gaia_train
    PURPOSE: To train
    INPUT:
        h5name: name of h5 data, {h5name}_train.h5   {h5name}_test.h5
        test (boolean): whether test data or not after training
        model: which model defined in astroNN.NN.cnn_model.py
        num_hidden = [] number of nodes in each of the hidden fully connected layers
        num_filters = [] number of filters used in the convolutional layers
        activation = activation function used every layer except for the output layers (https://keras.io/activations/)
        initializer = model weight initializer
        filter_length = length of the filters in the convolutional layers
        pool_length = length of the maxpooling window
        batch_size = number of spectra fed into model at once during training
        max_epochs = maximum number of interations for model training
        lr = initial learning rate for optimization algorithm
        early_stopping_min_delta
        early_stopping_patience
        reduce_lr_patience
        reduce_lr_min
        test=True!!
        cnn_visualization: whether do cnn visualization or not after training
        cnn_vis_num: number of spectra for cnn visualization!!Only has effect if and only if cnn_visualization=True!!
        test_noisy: whether of not test [train + noise + translation] data
    OUTPUT: model
    HISTORY:
        2017-Nov-09 Henry Leung
    """
    beta_1 = 0.9  # exponential decay rate for the 1st moment estimates for optimization algorithm
    beta_2 = 0.999  # exponential decay rate for the 2nd moment estimates for optimization algorithm
    optimizer_epsilon = 1e-08  # a small constant for numerical stability for optimization algorithm

    if h5name is None:
        raise ValueError('Please specift the dataset name using h5name="...... "')
    if model is None:
        model = 'cnn_apogee_1'
        print('No predefined model specified, using cnn_apogee_1 as default')
    if num_hidden is None:
        raise ValueError('Please specift a list of number of neurons using num_hidden=[.., ...], must be a list')
    if activation is None:
        activation = 'relu'
        print('activation not provided, using default activation={}'.format(activation))
    if initializer is None:
        initializer = 'he_normal'
        print('initializer not provided, using default initializer={}'.format(initializer))
    if filter_length is None:
        filter_length = 8
        print('filter_length not provided, using default filter_length={}'.format(filter_length))
    if pool_length is None:
        pool_length = 4
        print('pool_length not provided, using default pool_length={}'.format(pool_length))
    if batch_size is None:
        batch_size = 64
        print('pool_length not provided, using default batch_size={}'.format(batch_size))
    if max_epochs is None:
        max_epochs = 200
        print('max_epochs not provided, using default max_epochs={}'.format(max_epochs))
    if lr is None:
        lr = 1e-5
        print('lr [Learning rate] not provided, using default lr={}'.format(lr))
    if early_stopping_min_delta is None:
        early_stopping_min_delta = 5e-6
        print('early_stopping_min_delta not provided, using default early_stopping_min_delta={}'.format(lr))
    if early_stopping_patience is None:
        early_stopping_patience = 8
        print('early_stopping_patience not provided, using default early_stopping_patience={}'.format(lr))
    if reuce_lr_epsilon is None:
        reuce_lr_epsilon = 7e-3
        print('reuce_lr_epsilon not provided, using default reuce_lr_epsilon={}'.format(lr))
    if reduce_lr_patience is None:
        reduce_lr_patience = 2
        print('reduce_lr_patience not provided, using default reduce_lr_patience={}'.format(lr))
    if reduce_lr_min is None:
        reduce_lr_min = 7e-08
        print('reduce_lr_min not provided, using default reduce_lr_min={}'.format(lr))

    now = datetime.datetime.now()
    runno = 1
    for runno in range(1, 99999):
        folder_name = 'gaia_train_{}{:02d}_run{:03d}'.format(now.month, now.day, runno)
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            break
        else:
            runno += 1

    currentdir = os.getcwd()
    fullfilepath = os.path.join(currentdir, folder_name + '/')

    with open(fullfilepath + 'hyperparameter_{}{:02d}_run{}.txt'.format(now.month, now.day, runno), 'w') as h:
        h.write("model: {} \n".format(model))
        h.write("num_hidden: {} \n".format(num_hidden))
        h.write("num_filters: {} \n".format(num_filters))
        h.write("activation: {} \n".format(activation))
        h.write("initializer: {} \n".format(initializer))
        h.write("filter_length: {} \n".format(filter_length))
        h.write("pool_length: {} \n".format(pool_length))
        h.write("batch_size: {} \n".format(batch_size))
        h.write("max_epochs: {} \n".format(max_epochs))
        h.write("lr: {} \n".format(lr))
        h.write("early_stopping_min_delta: {} \n".format(early_stopping_min_delta))
        h.write("early_stopping_patience: {} \n".format(early_stopping_patience))
        h.write("reuce_lr_epsilon: {} \n".format(reuce_lr_epsilon))
        h.write("reduce_lr_min: {} \n".format(reduce_lr_min))
        h.close()

    h5data = h5name + '_train.h5'

    with h5py.File(h5data) as F:  # ensure the file will be cleaned up
        spectra = np.array(F['spectra'])

        # Dont do std, so equal 1 deliberately
        specpix_std = 1
        specpix_mean = np.median(spectra)
        spectra -= specpix_mean
        spectra /= specpix_std
        num_flux = spectra.shape[1]
        num_train = int(0.8 * spectra.shape[0])  # number of training example, rest are cross validation
        num_cv = spectra.shape[0] - num_train  # cross validation

        # load data
        absmag = np.array(F['absmag'])
        mean_labels = np.mean(absmag)
        std_labels = np.std(absmag)
        F.close()

    print('Each spectrum contains ' + str(num_flux) + ' wavelength bins')
    print('Training set includes ' + str(num_train) + ' spectra and the cross-validation set includes ' + str(num_cv)
          + ' spectra')

    mu_std = np.vstack((mean_labels, std_labels))
    spec_meanstd = np.vstack((specpix_mean, specpix_std))
    num_labels = mu_std.shape[1]

    # prevent Tensorflow taking up all the GPU memory
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    set_session(tf.Session(config=config))

    input_shape = (None, num_flux, 1)  # shape of input spectra that is fed into the input layer

    # model selection according to user-choice
    model = getattr(astroNN.NN.cnn_models, model)(input_shape, initializer, activation, num_filters, filter_length,
                                                  pool_length, num_hidden, num_labels)

    loss_function = 'mean_squared_error'

    # compute accuracy and mean absolute deviation
    metrics = ['mae']

    csv_logger = CSVLogger(fullfilepath + 'log.csv', append=True, separator=',')

    optimizer = Adam(lr=lr, beta_1=beta_1, beta_2=beta_2, epsilon=optimizer_epsilon, decay=0.0)

    early_stopping = EarlyStopping(monitor='val_loss', min_delta=early_stopping_min_delta,
                                   patience=early_stopping_patience, verbose=2, mode='min')

    reduce_lr = ReduceLROnPlateau(monitor='loss', factor=0.5, epsilon=reuce_lr_epsilon,
                                  patience=reduce_lr_patience, min_lr=reduce_lr_min, mode='min', verbose=2)

    model.compile(optimizer=optimizer, loss=loss_function, metrics=metrics)

    model.fit_generator(astroNN.NN.train_tools.generate_train_batch(num_train, batch_size, 0, mu_std, spectra, absmag),
                        steps_per_epoch=num_train / batch_size,
                        epochs=max_epochs,
                        validation_data=astroNN.NN.train_tools.generate_cv_batch(num_cv, batch_size, num_train, mu_std,
                                                                                 spectra, absmag),
                        max_queue_size=10, verbose=2, callbacks=[early_stopping, reduce_lr, csv_logger],
                        validation_steps=num_cv / batch_size)

    astronn_model = 'model_{}{:02d}_run{:03d}.h5'.format(now.month, now.day, runno)
    model.save(fullfilepath + astronn_model)
    print(astronn_model + ' saved to {}'.format(fullfilepath))
    np.save(fullfilepath + 'meanstd.npy', mu_std)
    np.save(fullfilepath + 'spectra_meanstd.npy', spec_meanstd)
    plot_model(model, show_shapes=True,
               to_file=fullfilepath + 'gaia_train_{}{:02d}_run{}.png'.format(now.month, now.day, runno))

    # visalize cnn filter
    if cnn_visualization is True:
        print('\n')
        print('Running astroNN.NN.cnn_visualization.cnn_visualization(), it may takes a while')
        astroNN.NN.cnn_visualization.cnn_gaia_visualization(h5name=h5name, folder_name=folder_name, num=cnn_vis_num)
        print('Finished, cnn visualization')

    # Test after training
    if test is True:
        print('\n')
        print('Running astroNN.NN.test.apogee_model_eval(), it may takes a while')
        astroNN.NN.test.gaia_model_eval(folder_name=folder_name, h5name=h5name)
        print('Finished plotting')
        print('\n')
    print('Finish running apogee_train()')

    return model
