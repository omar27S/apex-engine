"""R96 -- THE NINE SEATS: the pantry's breadth is law, and signed."""
from app.factory.factory import FactoryConfig


def test_the_nine_seats_are_the_default():
    assert FactoryConfig(pairs=("EURUSD",)).champion_seats == 9


def test_the_seats_change_the_signature():
    seven = FactoryConfig(pairs=("EURUSD",), champion_seats=7)
    nine = FactoryConfig(pairs=("EURUSD",), champion_seats=9)
    assert seven.signature() != nine.signature()
