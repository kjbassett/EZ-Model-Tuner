import pandas as pd

from EZMT import ModelTuner
import sys
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import OneHotEncoder
import numpy as np
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error as mse

from multiprocessing import freeze_support


def simulate_missing_data(data, chance):
    """
    Simulates missing data in a pandas dataframe by randomly removing a percentage of cells.

    Args:
    - df: pandas dataframe to simulate missing data for
    - chance: float between 0 and 1 representing the probability that a cell will be removed

    Returns:
    - df_miss: pandas dataframe with randomly missing values
    """
    np.random.seed(42)  # set seed for reproducibility
    df_miss = data.copy()  # create a copy of the original dataframe
    for i in range(df_miss.shape[0]):
        for j in range(df_miss.shape[1]):
            if np.random.rand() < chance:
                df_miss.iat[i, j] = np.nan  # randomly set value to NaN
    return df_miss


def MICE(x_train, x_test, max_iter, tolerance):
    imputer = IterativeImputer(
        max_iter=max_iter,
        tol=tolerance,
        random_state=42,
        estimator=RandomForestRegressor(),
        # verbose=True
    )
    imputer.fit(x_train)
    x_train = imputer.transform(x_train)
    x_test = imputer.transform(x_test)
    return x_train, x_test


def ord_transform(encoder, values):
    try:
        return encoder.transform(values)
    except ValueError:
        if hasattr(encoder, 'classes_'):
            encoder.fit(np.append(encoder.classes_, values))
        else:
            encoder.fit(values)
        return ord_transform(encoder, values)


def ordinal_encode(data, cols=None, encoders=None):
    if cols is None:
        cols = [col for col in data.columns if data[col].dtype == 'object']
    elif isinstance(cols, str):
        cols = [cols]
    if encoders is None:
        encoders = {}

    for col in cols:
        if col in encoders:
            le = encoders[col]
        else:
            le = LabelEncoder()
        data[col] = ord_transform(le, data[col])
        print('Are the mapping being updated in this scope or only in ord_transform?')
        encoders[col] = le  # Save the label encoder to decode later
    return data, encoders


def one_hot_encode(data, cols=None):
    if cols is None:
        cols = [col for col in data.columns if data[col].dtype == 'object']
    elif isinstance(cols, str):
        cols = [cols]
    encoders = {}
    for col in cols:
        encoder = OneHotEncoder(sparse_output=False)
        encoded = encoder.fit_transform(data[[col]])
        encoders[col] = encoder
        new_cols = [f"{col}_{cat}" for cat in encoder.categories_[0]]
        data[new_cols] = encoded
        data.drop(col, axis=1, inplace=True)
    return data, encoders


def oh_v_or(data, *args, cols=None):
    if cols is None:
        cols = [col for col in data.columns if data[col].dtype == 'object']
    elif isinstance(cols, str):
        cols = [cols]

    if len(args) != len(cols):
        raise Exception('args must same same length as cols')

    encoders = {}
    for i, col in enumerate(cols):
        if args[i]:  # 1
            _ = ordinal_encode(data, col)
        else:
            _ = one_hot_encode(data, col)

        data = _[0]
        encoders[col] = _[1][col]

    return data, encoders


def main():
    freeze_support()

    df = pd.read_csv('G:\\Programming\\mushroom.csv')
    df, encoders = oh_v_or(df, *[1 if col == 'class' else 0 for col in df.columns])

    mt = ModelTuner(None, df, 'class', generations=10, pop_size=20, goal='min')

    # add_step: self, func, inputs, outputs=None, *args, name=None
    # mt.add_step(one_hot_encode, 'x_train', ['x_train', 'encoders'], *[[0, 1] for _ in range(len(df.columns) - 1)])

    mt.add_decision_point(simulate_missing_data, 'smd_train', 'x_train', 'x_train', [(0.1, 0.95)])
    mt.add_decision_point(simulate_missing_data, 'smd_test', 'x_test', 'x_test', [(0.1, 0.95)])
    mt.add_decision_point(MICE, inputs=['x_train', 'x_test'], outputs=['x_train', 'x_test'], args=[[1, 2], (0.5, 1)])
    mt.add_decision_point(RandomForestRegressor, outputs='model', args=[range(10, 100)])  # todo try making model before adding decision points
    mt.add_decision_point('model.fit', inputs=['x_train', 'y_train'], outputs='model')
    mt.add_decision_point('model.predict', inputs='x_test', outputs='test_pred')
    mt.add_decision_point(mse, inputs=['test_pred', 'y_test'], outputs='score')

    results = mt.run()
    print(results.dna)
    print(results.knowledge.keys())
    print(results.score)
    print(results.fitness)

if __name__ == '__main__':
    main()

