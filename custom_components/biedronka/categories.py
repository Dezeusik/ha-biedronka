"""Przypisanie pozycji z paragonu do grup wydatków.

Nazwy na paragonach Biedronki są skrócone i pisane wielkimi literami (np. „MLEKO UHT 3,2% 1L”,
„PAP.TOAL.FOXY 8R”). Dopasowanie idzie po fragmentach słów; pierwsza pasująca grupa wygrywa,
a pozycja bez dopasowania trafia do „Jedzenie”.
"""
from __future__ import annotations

import re
import unicodedata

# grupa -> (kategoria w budżecie, fragmenty nazw)
GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Kaucja", "Drobne / różne", ("KAUCJA", "OPAKOWANIE ZWROTNE", "BUTELKA ZWR")),
    ("Torby", "Drobne / różne", ("TORBA", "REKLAMOWKA", "WOREK FOL")),
    ("Alkohol", "Jedzenie i chemia", ("PIWO", "WINO ", "WODKA", "WHISK", "LIKIER", "BRANDY", "RUM ", "GIN ",
                                      "NALEWKA", "CYDR", "SZAMPAN", "PROSECCO", "TYSKIE", "ZUBR", "ZYWIEC",
                                      "LECH ", "KOZEL", "HARNA", "WARKA", "OKOCIM", "PERLA", "SOPLICA",
                                      "ZOLADKOWA", "ZUBROWKA", "BOCIAN", "JACK D", "BALLANTINE")),
    ("Papierosy", "Drobne / różne", ("PAPIEROS", "L&M", "MARLBORO", "CHESTERFIELD", "IQOS", "HEETS", "TEREA",
                                     "WKLAD", "E-PAPIER", "TYTON", "GLO ")),
    ("Apteka i zdrowie", "Zdrowie i apteka", ("APAP", "IBUPROM", "IBUM", "PARACETAMOL", "NUROFEN", "WITAMIN",
                                              "MAGNEZ", "PLASTR", "BANDAZ", "TABL.", "SYROP", "TERMOMETR",
                                              "ELEKTROLIT", "PROBIOTYK", "MASECZK", "TEST CIAZ")),
    ("Chemia i higiena", "Jedzenie i chemia", ("PAP.TOAL", "PAPIER TOAL", "RECZNIK PAP", "RECZ.PAP", "CHUSTECZ",
                                               "CHUST.", "PROSZEK", "KAPS.DO PR", "KAPSULKI DO PR", "PLYN DO",
                                               "PL.DO", "PLYN NACZ", "ZMYWAR", "TABL.DO ZM", "DOMESTOS",
                                               "CILLIT", "LUDWIK", "FAIRY", "VANISH", "PERWOLL", "LENOR",
                                               "SILAN", "CIF ", "MLECZKO DO", "SZAMPON", "ODZYWKA", "MYDLO",
                                               "ZEL POD PR", "ZEL D/PR", "DEZODOR", "ANTYPERS", "PASTA DO Z",
                                               "SZCZOTECZ", "NIC DENT", "PODPASK", "TAMPON", "WKLADKI",
                                               "PIELUCH", "PIELUSZ", "PAMPERS", "DADA", "CHUSTECZKI NAW",
                                               "KREM DO", "KREM NIV", "NIVEA", "BALSAM", "GOLARK", "MASZYNK", "PIANKA DO GOL",
                                               "WOREK NA SMIE", "WORKI NA SMIE", "GABK", "SCIERK", "FOLIA ALU",
                                               "FOLIA SPOZ", "PAPIER DO PIEC", "ZAPACH", "ODSWIEZACZ",
                                               "KOSTKA WC", "ZAWIESZKA WC", "SOL DO ZMYW", "NABLYSZCZ")),
    ("Zabawki i prezenty", "Prezenty i zabawki", ("ZABAWK", "KLOCKI", "LALKA", "PLUSZ", "MASKOTK", "PUZZLE",
                                                   "GRA PLANSZ", "SAMOCHODZIK", "AUTKO", "FIGURK", "GANG ZAR",
                                                   "NAKLEJK", "KOLOROWANK", "BALON", "KARTKA OKOL", "TOREBKA PREZ",
                                                   "PAPIER PREZ", "LEGO", "PLASTELIN", "CIASTOLIN")),
    ("Szkoła i biuro", "Szkoła i wyprawka", ("ZESZYT", "KREDK", "DLUGOPIS", "OLOWEK", "FLAMAST", "MAZAK",
                                              "GUMKA DO M", "TEMPERO", "KLEJ W SZT", "BLOK RYS", "BLOK TECH",
                                              "FARBY", "PLECAK", "PIORNIK", "LINIJK", "NOZYCZK", "TECZK",
                                              "SEGREG", "PAPIER KSERO", "KALKULATOR")),
    ("Ubrania", "Ubrania i buty", ("SKARPET", "RAJSTOP", "MAJTK", "BOKSERK", "KOSZULK", "T-SHIRT", "BLUZ",
                                   "SPODNI", "LEGGINS", "PIZAM", "PIZAMA", "BIUSTON", "CZAPK", "RECKAWIC",
                                   "SZALIK", "KAPCI", "KLAPK", "BUTY", "SANDAL", "KURTK", "SUKIENK",
                                   "SPODENK", "DRES")),
    ("Dom i narzędzia", "Wyposażenie, remont, budowa", ("PARKSIDE", "WKRET", "WIERTARK", "WKRETARK", "KLUCZ",
                                                        "SRUBOKR", "POZIOMIC", "MLOTEK", "TASMA", "SILIKON",
                                                        "PIANKA MONT", "PRZEDLUZ", "LISTWA ZAS", "ZAROWK",
                                                        "ZAROWKA", "LED ", "BATERI", "LAMPK", "GARNEK",
                                                        "PATELN", "KUBEK", "TALERZ", "SZTUCC", "POJEMNIK",
                                                        "POSCIEL", "RECZNIK ", "KOC ", "PODUSZK", "DONICZK",
                                                        "ZIEMIA DO", "NASIONA", "SILVERCREST", "ERNESTO",
                                                        "LIVARNO", "CZAJNIK", "TOSTER", "MIKSER", "BLENDER",
                                                        "ODKURZ", "ZELAZK", "SUSZARK", "PRZEWOD", "KABEL",
                                                        "ŁADOWAR", "LADOWAR", "SLUCHAW")),
    ("Dla zwierząt", "Drobne / różne", ("KARMA", "DLA PSA", "DLA KOTA", "ZWIRK", "FELIX", "WHISKAS",
                                       "PEDIGREE", "SHEBA", "FRISKIES", "CESAR")),
    ("Słodycze i przekąski", "Jedzenie i chemia", ("CZEKOL", "BATON", "CUKIERK", "ZELK", "ŻELK", "LIZAK",
                                                    "CHIPS", "CHRUPK", "PALUSZK", "PRALINK", "WAFEL", "WAFL",
                                                    "CIASTK", "HERBATNIK", "DROPS", "GUMA DO ZUC", "LODY",
                                                    "LOD ", "RODZYN", "ORZESZ", "SNICKERS", "MARS ", "TWIX",
                                                    "KINDER", "PRINCESSA", "PRINCE POLO", "GRZESIEK", "MILKA",
                                                    "WEDEL", "HARIBO", "MENTOS", "TIC TAC", "SKITTLES",
                                                    "LAJKONIK", "PRINGLES", "LAYS", "CHEETOS", "KRAKERS",
                                                    "BISZKOPT", "DELICJE", "PIERNIK", "MARCEPAN", "BOMBONIER",
                                                    "TORCIK", "BABECZK", "PACZEK", "PĄCZEK", "DONUT", "CROISS",
                                                    "MUFFIN", "DESER")),
    ("Napoje", "Jedzenie i chemia", ("WODA ", "WODA MIN", "NAPOJ", "NAP.", "SOK ", "NEKTAR", "COCA", "PEPSI",
                                     "FANTA", "SPRITE", "7UP", "TIGER", "RED BULL", "MONSTER", "ENERGY",
                                     "OSHEE", "LIPTON", "TYMBARK", "KUBUS", "KUBUŚ", "HELLENA", "OPOLE",
                                     "KAWA", "HERBATA", "NESCAFE", "JACOBS", "TCHIBO", "KAKAO", "IZOTON",
                                     "LEMONIAD", "MUSZYNIANKA", "ZYWIEC ZDR", "CISOWIANKA", "NALECZOW",
                                     "KROPLA", "MINERAL")),
]

DEFAULT_GROUP = ("Jedzenie", "Jedzenie i chemia")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s)


_NORMED = [(g, cat, tuple(_norm(k) for k in keys)) for g, cat, keys in GROUPS]


def classify(name: str) -> tuple[str, str]:
    n = " " + _norm(name) + " "
    for group, cat, keys in _NORMED:
        for k in keys:
            if k in n:
                return group, cat
    return DEFAULT_GROUP
