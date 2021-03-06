import logging

import tensorflow as tf
from py_v8n import v8n

from src.sdav.input.InputGenerator import get_generator
from src.sdav.network.DenoisingAutoencoderVariant import DA


class SDA:

    def __init__(self,
                 input_shape: list,
                 hidden_units: list,
                 sparse_level: float = 0.05,
                 sparse_penalty: float = 1,
                 consecutive_penalty: float = 0.2,
                 batch_size: int = 10,
                 learning_rate: float = 0.1,
                 epochs: int = 100,
                 corruption_level: float = 0.3,
                 graph: tf.Graph = tf.Graph()):
        self._validate_params(input_shape, hidden_units, sparse_level, sparse_penalty, consecutive_penalty, batch_size,
                              learning_rate,
                              epochs, corruption_level)
        self._define_logger()
        logging.info("Initializing SDAV")

        self.input_shape = input_shape
        self.hidden_units = hidden_units
        self.sparse_level = sparse_level
        self.sparse_penalty = sparse_penalty
        self.consecutive_penalty = consecutive_penalty
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.corruption_level = corruption_level

        self._graph = graph

        self._define_model()

    def _define_logger(self):
        logging.basicConfig(filename='deepLoopCloser.log', format='%(asctime)s %(message)s',
                            datefmt='%m/%d/%Y %H:%M:%S')
        self.logger = logging.getLogger()
        self.logger.addHandler(logging.StreamHandler())
        self.logger.setLevel(logging.INFO)

    @staticmethod
    def _validate_params(input_shape: list, hidden_units: list,
                         sparse_level: float, sparse_penalty: float,
                         consecutive_penalty: float, batch_size: int,
                         learning_rate: float, epochs: int,
                         corruption_level: float):

        v8n().list_().length(2).every().int_().greater_than(0).validate(input_shape)
        v8n().list_().min_length(2).every().int_().greater_than(0).validate(hidden_units)

        is_positive_decimal = v8n().float_().positive()
        is_positive_decimal.validate(learning_rate, value_name="learning_rate")
        is_positive_decimal.validate(sparse_level, value_name="sparse_level")

        is_decimal_fraction = v8n().float_().between(0, 1)
        is_decimal_fraction.validate(sparse_penalty, value_name="sparse_penalty")
        is_decimal_fraction.validate(consecutive_penalty, value_name="consecutive_penalty")
        is_decimal_fraction.validate(corruption_level, value_name="corruption_level")

        is_positive_int = v8n().int_().positive()
        is_positive_int.validate(batch_size, value_name="batch_size")
        is_positive_int.validate(epochs, value_name="epochs")

    def _define_model(self):
        self._layers = []
        for i, hidden_units_n in enumerate(self.hidden_units):
            input_shape = self.input_shape if i == 0 else [self.input_shape[0], self.hidden_units[i - 1]]

            layer = DA(input_shape, hidden_units_n, sparse_level=self.sparse_level, sparse_penalty=self.sparse_penalty,
                       consecutive_penalty=self.consecutive_penalty, batch_size=self.batch_size,
                       learning_rate=self.learning_rate,
                       epochs=self.epochs, layer_n=i, corruption_level=self.corruption_level, graph=self._graph)

            self._layers.append(layer)

    def _create_dataset(self, file_pattern: str):
        with self._graph.as_default():
            generator = get_generator(file_pattern, self.input_shape)
            return tf.data.Dataset.from_generator(generator, tf.float64)

    def fit(self, file_pattern: str):
        logging.info("Fit SDAV")
        with self._graph.as_default():
            self._layers[0].fit(file_pattern)
            dataset = self._create_dataset(file_pattern)

            for i in range(1, len(self._layers)):
                layer = self._layers[i]
                previous_layer = self._layers[i - 1]
                dataset = dataset.map(lambda x: tf.py_func(previous_layer.transform, [x], tf.float64))
                layer.fit_dataset(dataset)
