"""Deterministic sample data so the product can be evaluated without paid APIs."""

SAMPLE_RESTAURANTS = [
    {"name":"Harbor & Hearth","address":"12 Atlantic Ave, Boston, MA","rating":4.7,"reviews_count":842,"price_level":"$$$","category":"New American","latitude":42.3601,"longitude":-71.0589,"sentiment_score":0.91,"sentiment_label":"Very Positive","sentiment_rationale":"Guests consistently praise food quality and hospitality.","menu_items":[{"item":"Seared Salmon","price":"$28"}],"reviews":[{"stars":5,"text":"Amazing fresh food and attentive service."}]},
    {"name":"Spice Route Kitchen","address":"88 Cambridge St, Boston, MA","rating":4.6,"reviews_count":618,"price_level":"$$","category":"Indian","latitude":42.3618,"longitude":-71.0575,"sentiment_score":0.88,"sentiment_label":"Very Positive","sentiment_rationale":"Strong flavor and value sentiment.","menu_items":[{"item":"Chicken Biryani","price":"$18"}],"reviews":[{"stars":5,"text":"Delicious authentic food and great value."}]},
    {"name":"North End Table","address":"41 Hanover St, Boston, MA","rating":4.4,"reviews_count":1210,"price_level":"$$$","category":"Italian","latitude":42.3637,"longitude":-71.0542,"sentiment_score":0.76,"sentiment_label":"Positive","sentiment_rationale":"Food performs well; wait-time complaints reduce sentiment.","menu_items":[{"item":"Truffle Tagliatelle","price":"$26"}],"reviews":[{"stars":4,"text":"Excellent pasta but the service was slow."}]},
    {"name":"Green Fork Cafe","address":"205 Boylston St, Boston, MA","rating":4.3,"reviews_count":286,"price_level":"$$","category":"Vegan","latitude":42.3519,"longitude":-71.0701,"sentiment_score":0.82,"sentiment_label":"Positive","sentiment_rationale":"Fresh ingredients and friendly service stand out.","menu_items":[{"item":"Harvest Bowl","price":"$15"}],"reviews":[{"stars":5,"text":"Fresh flavorful bowls and friendly staff."}]},
    {"name":"Beacon Street Tacos","address":"720 Beacon St, Boston, MA","rating":4.1,"reviews_count":394,"price_level":"$","category":"Mexican","latitude":42.3495,"longitude":-71.0991,"sentiment_score":0.67,"sentiment_label":"Positive","sentiment_rationale":"Value is praised, with mixed consistency feedback.","menu_items":[{"item":"Birria Tacos","price":"$13"}],"reviews":[{"stars":3,"text":"Good price but the food was cold once."}]},
    {"name":"Commonwealth Noodles","address":"9 Westland Ave, Boston, MA","rating":3.9,"reviews_count":177,"price_level":"$$","category":"Asian Fusion","latitude":42.3445,"longitude":-71.0844,"sentiment_score":0.54,"sentiment_label":"Mixed","sentiment_rationale":"Interesting menu but uneven speed and food quality.","menu_items":[{"item":"Miso Ramen","price":"$17"}],"reviews":[{"stars":3,"text":"Nice menu but slow service and bland broth."}]},
]


def demo_restaurants():
    return [dict(item) for item in SAMPLE_RESTAURANTS]

