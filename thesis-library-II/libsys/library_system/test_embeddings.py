# import os
# os.environ["HF_HUB_OFFLINE"] = "1"

# from sentence_transformers import SentenceTransformer, util

# model = SentenceTransformer('all-MiniLM-L6-v2')

# sentences = ["The library system is efficient.", "The system works well for books."]
# embeddings = model.encode(sentences)
# score = util.cos_sim(embeddings[0], embeddings[1])
# print("Similarity:", score.item())
# sentences = [
#     "The library system is efficient.",
#     "The library is very effective.",
#     "I love eating pizza."
# ]
# embeddings = model.encode(sentences)
# print("Efficient vs Effective:", util.cos_sim(embeddings[0], embeddings[1]).item())
# print("Efficient vs Pizza:", util.cos_sim(embeddings[0], embeddings[2]).item())
