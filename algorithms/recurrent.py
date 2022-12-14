import argparse
import auxil.mydata as mydata
import auxil.mymetrics as mymetrics
import gc
import keras.backend as K
from keras.callbacks import ModelCheckpoint
from keras.models import load_model
from keras.losses import categorical_crossentropy
from keras.layers import Dense, CuDNNGRU, CuDNNLSTM, Flatten, SimpleRNN
from keras.models import Sequential, Model
from keras.optimizers import Adam
from keras.utils import to_categorical as keras_to_categorical
import numpy as np
import sys


def set_params(args):
    args.batch_size = 100
    args.epochs = 150
    return args


def get_model_compiled(feat_size, seq_len, num_class, type_func):
    if type_func == "RNN":
        func = SimpleRNN
    elif type_func == "GRU":
        func = CuDNNGRU
    elif type_func == "LSTM":
        func = CuDNNLSTM
    else:
        print("NOT RECURRENT FUNC")
    clf = Sequential()
    clf.add(func(64, return_sequences=True, input_shape=(feat_size, seq_len)))
    clf.add(func(64, return_sequences=True))
    clf.add(Flatten())
    clf.add(Dense(num_class, activation='softmax'))
    clf.compile(loss=categorical_crossentropy,
                optimizer=Adam(), metrics=['accuracy'])
    return clf


def main():
    parser = argparse.ArgumentParser(description='Algorithms traditional ML')
    parser.add_argument('--dataset', type=str, required=True,
                        choices=["IP", "UP", "SV", "UH",
                                 "DIP", "DUP", "DIPr", "DUPr"],
                        help='dataset (options: IP, UP, SV, UH, DIP, DUP, DIPr, DUPr)')
    parser.add_argument('--type_recurrent', type=str, required=True,
                        choices=["RNN", "GRU", "LSTM"],
                        help='function (options: "RNN", "GRU", "LSTM")')
    parser.add_argument('--repeat', default=1, type=int, help='Number of runs')
    parser.add_argument('--components', default=None,
                        type=int, help='dimensionality reduction')
    parser.add_argument('--preprocess', default="standard",
                        type=str, help='Preprocessing')
    parser.add_argument('--splitmethod', default="sklearn",
                        type=str, help='Method for split datasets')
    parser.add_argument('--random_state', default=None, type=int,
                        help='The seed of the pseudo random number generator to use when shuffling the data')
    parser.add_argument('--tr_percent', default=0.15,
                        type=float, help='samples of train set')
    parser.add_argument('--use_val', action='store_true',
                        help='Use validation set')
    parser.add_argument('--val_percent', default=0.1,
                        type=float, help='samples of val set')
    parser.add_argument(
        '--verbosetrain', action='store_true', help='Verbose train')
    #########################################
    parser.add_argument('--set_parameters', action='store_false',
                        help='Set some optimal parameters')
    ############## CHANGE PARAMS ############
    parser.add_argument('--batch_size', default=100, type=int,
                        help='Number of training examples in one forward/backward pass.')
    parser.add_argument('--epochs', default=150, type=int,
                        help='Number of full training cycle on the training set')
    #########################################

    args = parser.parse_args()
    state = {k: v for k, v in args._get_kwargs()}

    if args.set_parameters:
        args = set_params(args)

    pixels, labels, num_class = \
        mydata.loadData(args.dataset, num_components=args.components,
                        preprocessing=args.preprocess)
    pixels = pixels.reshape(-1, pixels.shape[-1])

    stats = np.ones((args.repeat, num_class+3)) * -1000.0  # OA, AA, K, Aclass
    for pos in range(args.repeat):
        rstate = args.random_state+pos if args.random_state != None else None
        if args.dataset in ["UH", "DIP", "DUP", "DIPr", "DUPr"]:
            x_train, x_test, y_train, y_test = \
                mydata.load_split_data_fix(
                    args.dataset, pixels)  # , rand_state=args.random_state+pos)
        else:
            labels = labels.reshape(-1)
            pixels = pixels[labels != 0]
            labels = labels[labels != 0] - 1
            x_train, x_test, y_train, y_test = \
                mydata.split_data(
                    pixels, labels, args.tr_percent, rand_state=rstate)

        if args.use_val:
            x_val, x_test, y_val, y_test = \
                mydata.split_data(
                    x_test, y_test, args.val_percent, rand_state=rstate)
            x_val = x_val.reshape(x_val.shape[0], x_val.shape[1], 1)
        x_train = x_train.reshape(x_train.shape[0], x_train.shape[1], 1)
        x_test = x_test.reshape(x_test.shape[0], x_test.shape[1], 1)

        n_bands, sequences = x_train.shape[1:]
        clf = get_model_compiled(
            n_bands, sequences, num_class, args.type_recurrent)
        valdata = (x_val, keras_to_categorical(y_val, num_class)) if args.use_val else (
            x_test, keras_to_categorical(y_test, num_class))
        clf.fit(x_train, keras_to_categorical(y_train, num_class),
                batch_size=args.batch_size,
                epochs=args.epochs,
                verbose=args.verbosetrain,
                validation_data=valdata,
                callbacks=[ModelCheckpoint("/tmp/best_model.h5", monitor='val_accuracy', verbose=0, save_best_only=True)])
        del clf
        K.clear_session()
        gc.collect()
        clf = load_model("/tmp/best_model.h5")
        print("PARAMETERS", clf.count_params())
        stats[pos, :] = mymetrics.reports(
            np.argmax(clf.predict(x_test), axis=1), y_test)[2]
    # print(args.dataset, args.type_recurrent, list(stats[-1]))


if __name__ == '__main__':
    main()
