from process_to_plaintext import filter_english_words, is_likely_english_word

test_texts = [
    "Esta es una receta tradicional dominicana con rice and beans",
    "El mangú es un dish típico que se prepara con plátanos verdes",
    "You can find this recipe en la cocina de mi abuela",
    "Los ingredients principales son: yuca, pollo, y cilantro",
    "This is completely in English and should be filtered heavily",
    "La República Dominicana tiene beautiful beaches y cultura rica"
]

print("=" * 70)
print("Testing English Word Filtering")
print("=" * 70)

for i, text in enumerate(test_texts, 1):
    print(f"\n{i}. Original:")
    print(f"   {text}")
    filtered = filter_english_words(text)
    print(f"   Filtered:")
    print(f"   {filtered}")

print("\n" + "=" * 70)
print("Individual Word Tests")
print("=" * 70)

test_words = [
    "recipe", "receta", "rice", "arroz", "beans", "habichuelas",
    "dish", "plato", "ingredients", "ingredientes", "beautiful", "hermoso",
    "Dominican", "dominicano", "mangú", "yuca", "cilantro"
]

for word in test_words:
    is_english = is_likely_english_word(word)
    print(f"{word:15} -> {'ENGLISH (filtered)' if is_english else 'Spanish (kept)'}")
