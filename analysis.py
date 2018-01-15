"""
Analysis code for titanic dataset.
"""

# Data wrangling
import pandas as pd

# Visualization
import matplotlib.pyplot as plt
import seaborn as sea
import sys

# Machine learning
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.feature_selection import SelectFromModel
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

TRAIN_PATH = "data/train.csv"
TEST_PATH = "data/test.csv"
KFOLD = 10
RANDOM_STATE = 123

#####################
# Analysis tools

def printDiscreteStats(df, colName):
    """
    Print tally for column, and see relationship against label.
    The label is hardcoded to 'Survived'.
    @param df (dataframe)
    @param colName (string) - a feature column in 'df'.
    """
    print(df[[colName, 'Survived']] \
        .groupby([colName]) \
        .agg(['mean', 'count']) \
        .sort_values(
                by=[('Survived', 'mean')],
                ascending=False))

#####################
# Understand the data
def printPrelimAnalysis(df):
    """
    Preliminary analysis. Just visualizations before we wrangle anything.
    @param df (dataframe)
    """
    print("The column names are {0}".format(df.columns.values))
    # See first few rows.
    df.head()
    # Schema of the dataframe
    df.info()
    # Stats like means, etc for each column.
    # Can also see missing data from 'count'
    # Need 'all' so categorical columns like Name is included.
    df.describe(include='all')
    
    # For each feature, check distribution against label,
    # to see if feature is promising.
    # Each class, percent survival.
    df[['Pclass', 'Survived']] \
        .groupby(['Pclass'], as_index=False) \
        .mean() \
        .sort_values(by='Survived', ascending=False)
    # Each gender, percent survival.
    df[['Sex', 'Survived']] \
        .groupby(['Sex'], as_index=False) \
        .mean() \
        .sort_values(by='Survived', ascending=False)
    
    # Plot histogram
    g = sea.FacetGrid(df, col='Survived')
    g.map(plt.hist, 'Age', bins=20)
    
    # Break histogram down with another dimension.
    g = sea.FacetGrid(df, row='Pclass', col='Survived')
    # Alpha = transparency
    g.map(plt.hist, 'Age', alpha=.5, bins=20)
    
    # Point plot. Show survival rate for [embarkations, pclass, gender]
    # This means there's a chart / row per embarkation
    g = sea.FacetGrid(df, row = 'Embarked')
    # x = Pclass, y = Survived, breakdown = Sex
    # Without palette, the color difference is not that striking
    g.map(sea.pointplot, 'Pclass', 'Survived', 'Sex', palette='deep')
    # So the gender legend shows up
    g.add_legend()
    
    # Bar chart.
    g = sea.FacetGrid(df, row='Embarked', col='Survived')
    # If ci (confidence interval) exists, there is a vertical line on every bar.
    g.map(sea.barplot, 'Sex', 'Fare', alpha=.5, ci=None)

"""
Plot variable importance by training decisision tree.
@param X (DataFrame). The feature set.
@param y (DataFrame). The labels.
"""
def plot_variable_importance( X , y ):
    max_num_features = 20
    model = DecisionTreeClassifier()
    model.fit( X , y )
    imp = pd.DataFrame( 
        model.feature_importances_  , 
        columns = [ 'Importance' ] , 
        index = X.columns 
    )
    imp = imp.sort_values( [ 'Importance' ] , ascending = True )
    imp[ : max_num_features ].plot( kind = 'barh' )
    print ("Tree model score on training set: {0}".format(
            model.score( X , y )))
    


#####################
# Data wrangling
def impute_age(src_df, dst_df):
    """
    Impute missing age values.
    @param src_df (DataFrame). The data frame to gather statistics from.
    @return dst_df(DataFrame) The data frames to modify.
    """
    # Impute age based on the median age in the [Sex, Pclass] group
    for sex in src_df['Sex'].unique():
        for pclass in src_df['Pclass'].unique():
            for title in src_df['Title'].unique():
                # The bitwise operator (instead of 'and') is actually required.
                # https://stackoverflow.com/a/36922103
                guess_age =  \
                    src_df[(src_df['Sex'] == sex) & \
                       (src_df['Pclass'] == pclass) & \
                       (src_df['Title'] == title)]['Age'].dropna().median()
                dst_df.loc[dst_df['Age'].isnull() & \
                   (dst_df['Sex'] == sex) & \
                   (dst_df['Pclass'] == pclass) & \
                   (dst_df['Title'] == title),\
                 'Age'] = guess_age

def impute_embarked(src_df, dst_df):
    """
    Impute missing embarkation values.
    @param src_df (DataFrame). The data frame to gather statistics from.
    @return dst_df (DataFrame) The data frames to modify.
    """
    freq_port = src_df.Embarked.dropna().mode()[0]
    dst_df['Embarked'].fillna(freq_port, inplace=True)

def impute_fare(src_df, dst_df):
    """
    Impute missing fare values.
    The train set is complete, but test set has 1 missing value.
    @param src_df (DataFrame). The data frame to gather statistics from.
    @return dst_df (DataFrame) The data frames to modify.
    """
    dst_df['Fare'].fillna(src_df['Fare'].dropna().median(), inplace=True)

def add_age_group(df):
    df.loc[df['Age'] <= 16, 'AgeGroup'] = "kids (<=16)"
    df.loc[(df['Age'] > 16) & (df['Age'] <= 50), 'AgeGroup'] = "adults (>16,<= 50)"
    df.loc[df['Age'] > 50, 'AgeGroup'] = "elderly (>50)"
    df['AgeGroup'] = df['AgeGroup'].astype('category')

def add_title(df):
    df['Title'] = df['Name'].str.extract('([A-Za-z]+)\.', expand=False)
    df['Title'] = df['Title'].replace(['Lady', 'Countess','Capt', 'Col',\
 	'Don', 'Dr', 'Major', 'Rev', 'Sir', 'Jonkheer', 'Dona'], 'Rare')
    df['Title'] = df['Title'].replace('Mlle', 'Miss')
    df['Title'] = df['Title'].replace('Ms', 'Miss')
    df['Title'] = df['Title'].replace('Mme', 'Mrs')
    df['Title'] = df['Title'].replace(['Lady', 'Countess','Capt', 'Col',\
      'Don', 'Dr', 'Major', 'Rev', 'Sir', 'Jonkheer', 'Dona'], 'Rare')
    df['Title'] = df['Title'].astype('category')

def add_is_alone(df):
    family_size_lst = df['SibSp'] + df['Parch'] + 1
    df['IsAlone'] = 0
    df.loc[family_size_lst == 1, 'IsAlone'] = 1
    
def update_features(src_df, dst_df):
    """
    Drop, add, modify columns. To be applied on both training and test set.
    This form is not dependent on the learning model, and is also a friendly
    format to do plots and analyses on, as the enums are in legible forms.
    So, more processing like 'onehot_categories' might be needed.
    @param src_df (DataFrame). The data frame to gather statistics from.
    @param dst_df (DataFrame) The data frames to modify.
    @return dst_df The updated dst_df.
    Side-effect - Will modify dst_df, but you have to reassign with the return
    value. Idk how to select columns and mutate dst_df :/
    """
    # Title needed for age imputation
    add_title(src_df)
    add_title(dst_df)
    impute_age(src_df, dst_df)
    add_age_group(dst_df)
    impute_embarked(src_df, dst_df)
    impute_fare(src_df, dst_df)    
    add_is_alone(dst_df)
    dst_df['Pclass'] = dst_df['Pclass'].astype('category')
    dst_df['Embarked'] = dst_df['Embarked'].astype('category')
    dst_df['Sex'] = dst_df['Sex'].astype('category')
    
    # Select features
    dst_df = dst_df[[
            'Age',
            'AgeGroup',
            'Embarked',
            'Fare',
            'IsAlone',
            'Pclass',
            'Sex',
            'Title'
            ]].copy()
    return dst_df

def numerize_categories(df):    
    """
    Convert all categorical columns to their codes.
    Some learning models hate strings.
    Note that some learning models do not handle enums, and you might have to
    use 'onehot_categories()' instead.
    @param df (DataFrame).
    """
    cat_columns = df.select_dtypes(['category']).columns
    df[cat_columns] = df[cat_columns].apply(lambda x: x.cat.codes)
    
def onehot_categories(df):    
    """
    Apply one-hot encoding to all categorical columns.
    Some sklearn models don't deal with categories.
    E.g. As of Jan 2018, even random forest implementation converts enums
      to floats. tps://github.com/scikit-learn/scikit-learn/pull/4899
    @param df (DataFrame).
    @return df new pd with categorical columns replaced with binaries.
    """
    cat_cols = df.select_dtypes(['category']).columns
    # drop_first to reduce number of dependent features. The last item can be
    # inferred. We could do better by maybe not just dropping arbitrarily.
    # E.g. keep the one that has the highest variable importance? Or drop the
    # one with highest occurrence.
    dummied_cat_df = pd.get_dummies(df[cat_cols], drop_first = True)
    dummied_pd = pd.concat([df, dummied_cat_df], axis=1)
    dummied_pd.drop(cat_cols, axis=1, inplace=True)
    return dummied_pd

#####################
# Model generation and evalution

def evaluate_models(models, nfold, features, labels):
    """
    Perform k-fold on models, 
    Print K-fold accuracy for models.
    @param nfold (int) k in kfold
    @param models (Map<string, model>) Models to evaluate.
    @param features, labels. X,Y of training set.
    """
    model_scores = {}
    kfold = StratifiedKFold(n_splits=nfold, random_state = RANDOM_STATE)
    for model_name in models:
        total_score = 0
        for train_index, test_index in kfold.split(features, labels):
            x_train = features.iloc[train_index,:]
            x_test = features.iloc[test_index,:]
            y_train = labels.iloc[train_index]
            y_test = labels.iloc[test_index]
            models[model_name].fit(x_train, y_train)
            cur_score = models[model_name].score(x_test, y_test)
            total_score += cur_score
            print("Model {0}. Acc {1}".format(model_name, cur_score))
        model_scores[model_name] = total_score / nfold
    
    desc_score_models = sorted(model_scores, key=model_scores.get, reverse=True)
    for model in desc_score_models:
        print(model, model_scores[model])
        
def gen_models():
    """
    Create untrained models
    
    @return (Map<string, model>) Models to evaluate.
    """
    models = {
        "SVM": SVC(random_state=RANDOM_STATE),
        # See grid_search_forest()
        "Random forest": RandomForestClassifier(n_estimators=50,
                                                max_features=2,
                                                random_state=RANDOM_STATE)
        }
    return models

def grid_search_forest(features, labels):
    """
    Grid search on random forest to find the best hyperparams.
    This is just an analysis tool.
    With this hyperparam, add it to the models.
    
    Note: It is kind of cheating that we optimize the hyperparams based on
    the same set we will later do kfold-evaluation on huh.

    Jan 14, 2018
    Out: Best parameters set found on development set:
        {'max_features': 2, 'n_estimators': 50}
    
    @param models (Map<string, model>) Models to evaluate.
    @param features, labels. X,Y of training set.
    """
    forest_params = {'n_estimators': [25, 50, 100, 250, 500],
                     'max_features': [2,3,5]}
    cv_model = GridSearchCV(\
                RandomForestClassifier( \
                        random_state=RANDOM_STATE), forest_params, cv=5,\
                       scoring='accuracy')
    cv_model.fit(features, labels)
    print("Best parameters set found on development set:")
    print(cv_model.best_params_)
    
def write_submission(model, train_features, train_labels, test_features,
                     passenger_ids): 
    """
    Write the final submission.
    @param model (Model) - the best learning model to use
    @param train_features (DataFrame) - the features to train model with
    @param train_labels (DataFrame) - the labels to train model with
    @param test_features (DataFrame) - the test features to predict against
    @param passenger_ids (List<Int>) - The passenger ids
    """
    model.fit(train_features, train_labels)
    final_labels = model.predict(test_features)
    submission = pd.DataFrame({
            "PassengerId": passenger_ids,
            "Survived": final_labels
            })
    submission.to_csv('output/submission.csv', index=False)

"""
Main
"""
raw_train_df = pd.read_csv(TRAIN_PATH)
raw_test_df = pd.read_csv(TEST_PATH)
train_df = raw_train_df.copy()
test_df = raw_test_df.copy()

train_features = onehot_categories(
        update_features(raw_train_df, train_df))
test_features = onehot_categories(
        update_features(raw_train_df, test_df))
train_labels = raw_train_df["Survived"]

# Auto feature selection
clf = ExtraTreesClassifier(random_state=RANDOM_STATE)
clf = clf.fit(train_features, train_labels)
feature_select_model = SelectFromModel(clf, prefit=True)
reduced_cols = train_features.columns[feature_select_model.get_support()]
train_reduced_features = train_features[reduced_cols]
test_reduced_features = test_features[reduced_cols]

# Enable if you want to see variable importance
"""
plot_variable_importance(train_reduced_features, train_labels)
sys.exit()
"""

# Generate models
models = gen_models()

# Enable if you want to tune hyperparams.
"""
grid_search_forest(train_reduced_features, train_labels)
sys.exit()
"""

evaluate_models(models, KFOLD, train_reduced_features, train_labels)

# Final training and prediction
final_model = models['Random forest']
write_submission(final_model, train_reduced_features, train_labels,
                 test_reduced_features, raw_test_df["PassengerId"])
