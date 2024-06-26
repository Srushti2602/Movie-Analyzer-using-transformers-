# -*- coding: utf-8 -*-
"""movie analyzer .ipynb

Automatically generated by Colaboratory.


# Analyzing movie reviews using transformers

This problem asks you to train a sentiment analysis model using the BERT (Bidirectional Encoder Representations from Transformers) model, introduced [here](https://arxiv.org/abs/1810.04805). Specifically, we will parse movie reviews and classify their sentiment (according to whether they are positive or negative.)

We will use the [Huggingface transformers library](https://github.com/huggingface/transformers) to load a pre-trained BERT model to compute text embeddings, and append this with an RNN model to perform sentiment classification.

## Data preparation

Before delving into the model training, let's first do some basic data processing. The first challenge in NLP is to encode text into vector-style representations. This is done by a process called *tokenization*.
"""

import torch
import random
import numpy as np

SEED = 1234

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True

"""Let us load the transformers library first."""

!pip install transformers

"""Each transformer model is associated with a particular approach of tokenizing the input text.  We will use the `bert-base-uncased` model below, so let's examine its corresponding tokenizer.


"""

from transformers import BertTokenizer

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

"""The `tokenizer` has a `vocab` attribute which contains the actual vocabulary we will be using. First, let us discover how many tokens are in this language model by checking its length."""

print("Size of vocabulary:", len(tokenizer.vocab))
# The tokenizer's vocabulary is accessible via its vocab attribute.
# This is a dictionary where keys are tokens and values are the token IDs.

"""Using the tokenizer is as simple as calling `tokenizer.tokenize` on a string. This will tokenize and lower case the data in a way that is consistent with the pre-trained transformer model."""

tokens = tokenizer.tokenize('Hello WORLD how ARE yoU?')

print(tokens)

"""We can numericalize tokens using our vocabulary using `tokenizer.convert_tokens_to_ids`."""

indexes = tokenizer.convert_tokens_to_ids(tokens)

print(indexes)

"""The transformer was also trained with special tokens to mark the beginning and end of the sentence, as well as a standard padding and unknown token.

Let us declare them.
"""

init_token = tokenizer.cls_token
eos_token = tokenizer.sep_token
pad_token = tokenizer.pad_token
unk_token = tokenizer.unk_token

print(init_token, eos_token, pad_token, unk_token)

"""We can call a function to find the indices of the special tokens."""

init_token_idx = tokenizer.convert_tokens_to_ids(init_token)
eos_token_idx = tokenizer.convert_tokens_to_ids(eos_token)
pad_token_idx = tokenizer.convert_tokens_to_ids(pad_token)
unk_token_idx = tokenizer.convert_tokens_to_ids(unk_token)

print(init_token_idx, eos_token_idx, pad_token_idx, unk_token_idx)

"""We can also find the maximum length of these input sizes by checking the `max_model_input_sizes` attribute (for this model, it is 512 tokens)."""

max_input_length = tokenizer.max_model_input_sizes['google-bert/bert-base-uncased']

"""Let us now define a function to tokenize any sentence, and cut length down to 510 tokens (we need one special `start` and `end` token for each sentence)."""

def tokenize_and_cut(sentence):
    tokens = tokenizer.tokenize(sentence)
    tokens = tokens[:max_input_length-2]
    return tokens

"""Finally, we are ready to load our dataset. We will use the [IMDB Moview Reviews](https://huggingface.co/datasets/imdb) dataset. Let us also split the train dataset to form a small validation set (to keep track of the best model)."""

#%pip install -q torchtext==0.6.0

from torchtext import data, datasets
from torchtext.vocab import Vocab
TEXT = data.Field(batch_first=True,
         use_vocab=False,
         tokenize=tokenize_and_cut,
         preprocessing=tokenizer.convert_tokens_to_ids,
         init_token=init_token_idx,
         eos_token=eos_token_idx,
         pad_token=pad_token_idx,
         unk_token=unk_token_idx)
LABEL = data.LabelField(dtype=torch.float)

train_data, test_data = datasets.IMDB.splits(TEXT, LABEL)

train_data, valid_data = train_data.split(random_state = random.seed(SEED))

"""Let us examine the size of the train, validation, and test dataset."""

print ("Number of data points in the train set:",len(train_data))
print("Number of data points in the test set:",len(test_data))
print("Number of data points in the validation set:",len(valid_data))

"""We will build a vocabulary for the labels using the `vocab.stoi` mapping."""

LABEL.build_vocab(train_data)

print(LABEL.vocab.stoi)

"""Finally, we will set up the data-loader using a (large) batch size of 128. For text processing, we use the `BucketIterator` class."""

BATCH_SIZE = 128

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

train_iterator, valid_iterator, test_iterator = data.BucketIterator.splits(
    (train_data, valid_data, test_data),
    batch_size = BATCH_SIZE,
    device = device)

"""## Model preparation

We will now load our pretrained BERT model. (Keep in mind that we should use the same model as the tokenizer that we chose above).
"""

from transformers import BertTokenizer, BertModel

bert = BertModel.from_pretrained('bert-base-uncased')

"""As mentioned above, we will append the BERT model with a bidirectional GRU to perform the classification."""

import torch.nn as nn

class BERTGRUSentiment(nn.Module):
    def __init__(self,bert,hidden_dim,output_dim,n_layers,bidirectional,dropout):

        super().__init__()

        self.bert = bert

        embedding_dim = bert.config.to_dict()['hidden_size']

        self.rnn = nn.GRU(embedding_dim,
                          hidden_dim,
                          num_layers = n_layers,
                          bidirectional = bidirectional,
                          batch_first = True,
                          dropout = 0 if n_layers < 2 else dropout)

        self.out = nn.Linear(hidden_dim * 2 if bidirectional else hidden_dim, output_dim)

        self.dropout = nn.Dropout(dropout)

    def forward(self, text):

        #text = [batch size, sent len]

        with torch.no_grad():
            embedded = self.bert(text)[0]

        #embedded = [batch size, sent len, emb dim]

        _, hidden = self.rnn(embedded)

        #hidden = [n layers * n directions, batch size, emb dim]

        if self.rnn.bidirectional:
            hidden = self.dropout(torch.cat((hidden[-2,:,:], hidden[-1,:,:]), dim = 1))
        else:
            hidden = self.dropout(hidden[-1,:,:])

        #hidden = [batch size, hid dim]

        output = self.out(hidden)

        #output = [batch size, out dim]

        return output

"""Next, we'll define our actual model.

Our model will consist of

* the BERT embedding (whose weights are frozen)
* a bidirectional GRU with 2 layers, with hidden dim 256 and dropout=0.25.
* a linear layer on top which does binary sentiment classification.

Let us create an instance of this model.
"""

# insert code here
HIDDEN_DIM = 256  # Example: Set the hidden dimension for the GRU layers
OUTPUT_DIM = 1    # Output dimension for binary classification (0 or 1)
N_LAYERS = 2      # Number of GRU layers
BIDIRECTIONAL = True  # Specify if the GRU should be bidirectional
DROPOUT = 0.5    # Dropout rate for regularization

model = BERTGRUSentiment(bert,
                         HIDDEN_DIM,
                         OUTPUT_DIM,
                         N_LAYERS,
                         BIDIRECTIONAL,
                         DROPOUT)

"""We can check how many parameters the model has."""

# p.numel() returns the total number of elements in the parameter tensor, which is a measure of the parameter's size
# The sum() function then adds up these numbers to get the total count of trainable elements
def count_trainable_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'The model has {count_trainable_parameters(model):,} trainable parameters.')
# Now, we call the function we defined earlier and print out the number of trainable parameters.
# We use formatted string literals (f-strings) with :, which includes a comma as a thousand separator for better readability.

"""Oh no~ if you did this correctly, youy should see that this contains *112 million* parameters. Standard machines (or Colab) cannot handle such large models.

However, the majority of these parameters are from the BERT embedding, which we are not going to (re)train. In order to freeze certain parameters we can set their `requires_grad` attribute to `False`. To do this, we simply loop through all of the `named_parameters` in our model and if they're a part of the `bert` transformer model, we set `requires_grad = False`.
"""

for name, param in model.named_parameters():
    if name.startswith('bert'):
        param.requires_grad = False

# Freeze the BERT model's parameters
for param in model.bert.parameters():
    param.requires_grad = False

# Re-use the function to count the number of trainable parameters
# Now it will only count parameters that were not part of the BERT model
remaining_trainable_parameters = count_trainable_parameters(model)

# Print the number of remaining trainable parameters after freezing BERT parameters
print(f'The model has {remaining_trainable_parameters:,} trainable parameters after freezing BERT.')

"""We should now see that our model has under 3M trainable parameters. Still not trivial but manageable.

## Train the Model

All this is now largely standard.

We will use:
* the Binary Cross Entropy loss function: `nn.BCEWithLogitsLoss()`
* the Adam optimizer

and run it for 2 epochs (that should be enough to start getting meaningful results).
"""

import torch.optim as optim

optimizer = optim.Adam(model.parameters())

criterion = nn.BCEWithLogitsLoss()

model = model.to(device)
criterion = criterion.to(device)

"""
Also, define functions for:
* calculating accuracy.
* training for a single epoch, and reporting loss/accuracy.
* performing an evaluation epoch, and reporting loss/accuracy.
* calculating running times."""

def binary_accuracy(preds, y):
    # Round predictions to the closest integer (0 or 1) using the sigmoid function
    # torch.round() will round the values to 0/1
    # The sigmoid function will convert logits into probabilities between 0 and 1
    rounded_preds = torch.round(torch.sigmoid(preds))

    # Compare rounded predictions to the actual labels
    # We use the eq method to check if the values are equal; it returns a tensor of the same size
    # containing elements of value 1 for equal elements, and 0 otherwise
    correct = (rounded_preds == y).float()  # we cast the result to float to perform the division

    # Calculate the accuracy
    # torch.mean() calculates the mean of the elements in the input tensor
    acc = correct.mean()

    return acc

def train(model, iterator, optimizer, criterion):
    epoch_loss = 0
    epoch_acc = 0

    # Set the model in training mode
    model.train()

    for batch in iterator:

        text,labels=batch.text.to(device),batch.label.to(device)
        # Resets the gradients after every batch
        optimizer.zero_grad()

        # Convert to 1D tensor
        predictions = model(text).squeeze(1)

        # Compute the loss
        loss = criterion(predictions, labels.float())

        # Compute the binary accuracy
        acc = binary_accuracy(predictions,labels)

        # Backpropagate the loss and compute the gradients
        loss.backward()

        # Update the weights
        optimizer.step()

        # Accumulate loss and accuracy
        epoch_loss += loss.item()
        epoch_acc += acc.item()

    # Return the average loss and accuracy
    return epoch_loss / len(iterator), epoch_acc / len(iterator)

def evaluate(model, iterator, criterion):
    epoch_loss = 0
    epoch_acc = 0

    # Set the model in evaluation mode
    model.eval()

    # Deactivate autograd
    with torch.no_grad():

        for batch in iterator:

            text,labels=batch.text.to(device),batch.label.to(device)

            # Convert to 1D tensor
            predictions = model(text).squeeze(1)

            # Compute loss and accuracy
            loss = criterion(predictions, labels.float())
            acc = binary_accuracy(predictions, labels)

            # Accumulate loss and accuracy
            epoch_loss += loss.item()
            epoch_acc += acc.item()

    # Return the average loss and accuracy
    return epoch_loss / len(iterator), epoch_acc / len(iterator)

import time

def epoch_time(start_time, end_time):
    elapsed_time = end_time - start_time
    elapsed_mins = int(elapsed_time / 60)
    elapsed_secs = int(elapsed_time - (elapsed_mins * 60))
    return elapsed_mins, elapsed_secs

"""We are now ready to train our model.

**Statutory warning**: Training such models will take a very long time since this model is considerably larger than anything we have trained before. Even though we are not training any of the BERT parameters, we still have to make a forward pass. This will take time; each epoch may take upwards of 30 minutes on Colab.

Let us train for 2 epochs and print train loss/accuracy and validation loss/accuracy for each epoch. Let us also measure running time.

Saving intermediate model checkpoints using  

`torch.save(model.state_dict(),'model.pt')`

may be helpful with such large models.
"""

N_EPOCHS = 2

best_valid_loss = float('inf')

for epoch in range(N_EPOCHS):

    # Start the timer for the epoch
    start_time = time.time()

    # Perform training and validation
    train_loss, train_acc = train(model, train_iterator, optimizer, criterion)
    valid_loss, valid_acc = evaluate(model, valid_iterator, criterion)

    # End the timer for the epoch
    end_time = time.time()

    # Calculate the time taken for the epoch
    epoch_mins, epoch_secs = divmod(end_time - start_time, 60)

    # If the validation loss is the best we've seen, save the model state dict
    if valid_loss < best_valid_loss:
        best_valid_loss = valid_loss
        torch.save(model.state_dict(), 'model.pt')

    # Print the metrics and timing for the epoch
    print(f'Epoch: {epoch+1:02} | Epoch Time: {int(epoch_mins)}m {int(epoch_secs)}s')
    print(f'\tTrain Loss: {train_loss:.3f} | Train Acc: {train_acc*100:.2f}%')
    print(f'\tVal. Loss: {valid_loss:.3f} |  Val. Acc: {valid_acc*100:.2f}%')

"""Load the best model parameters (measured in terms of validation loss) and evaluate the loss/accuracy on the test set."""

model.load_state_dict(torch.load('model.pt'))

test_loss, test_acc = evaluate(model, test_iterator, criterion)

print(f'Test Loss: {test_loss:.3f} | Test Acc: {test_acc*100:.2f}%')

"""## Inference

We'll then use the model to test the sentiment of some fake movie reviews. We tokenize the input sentence, trim it down to length=510, add the special start and end tokens to either side, convert it to a `LongTensor`, add a fake batch dimension using `unsqueeze`, and perform inference using our model.
"""

def predict_sentiment(model, tokenizer, sentence):
    model.eval()
    tokens = tokenizer.tokenize(sentence)
    tokens = tokens[:max_input_length-2]
    indexed = [init_token_idx] + tokenizer.convert_tokens_to_ids(tokens) + [eos_token_idx]
    tensor = torch.LongTensor(indexed).to(device)
    tensor = tensor.unsqueeze(0)
    prediction = torch.sigmoid(model(tensor))
    return prediction.item()

predict_sentiment(model, tokenizer, "Justice League is terrible. I hated it.")

predict_sentiment(model, tokenizer, "Avengers was great!!")

"""Great! Try playing around with two other movie reviews (you can grab some off the internet or make up text yourselves), and see whether your sentiment classifier is correctly capturing the mood of the review."""

predict_sentiment(model, tokenizer, "Anabella was okay for me, its not that scary !")

predict_sentiment(model, tokenizer, " jurazzic park movie is my all time favourite ")

"""Conclusion: In summary, the movie analyzer developed using transformer models has demonstrated a notable capability to interpret and classify complex movie-related data with high accuracy. Leveraging the contextual understanding afforded by transformers, the system provides valuable insights into movie trends and audience reception. While challenges such as data variability and nuanced language interpretation present ongoing opportunities for refinement, the potential applications of this technology in the film industry—from targeted marketing to content recommendation systems—are substantial. Future enhancements will focus on expanding the dataset and refining the model's interpretative algorithms, with the ultimate goal of achieving an even deeper understanding of cinematic storytelling and its impact on viewers. After the implementation of the BERT model the train accuracy is Train Acc: 88.68% and test acc is 89.46% . In all it took 27 minutes to train the model . The predicted sentiment of by the model of the given statement is 94.12%."""
