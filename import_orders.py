"""
Importação de pedidos históricos → tabela orders, order_items, order_status_history
Também atualiza:
  - customers.notes  ← coluna "da onde eu conheço"
  - products.description ← coluna "obs"

Uso:
    cd backend
    py import_orders.py                           # importa do XLSX padrão
    py import_orders.py --file historico.xlsx     # outro arquivo
    py import_orders.py --dry-run                 # só mostra o que seria feito
    py import_orders.py --reset                   # apaga TODOS os pedidos antes de importar

Dependências extras:
    pip install pandas openpyxl rapidfuzz

Formato do XLSX esperado (colunas, 0-indexadas):
    col 0: número do pedido
    col 1: data pedido   (ex: 22/8/2014)
    col 2: data término  (ignorada)
    col 3: data entrega  (ignorada)
    col 4: vazio
    col 5: nome do cliente
    col 6: descrição do pedido (ex: "1 Elsa e 1 Anna")
    col 7: quantidade total
    col 8: tempo de execução (ignorado)
    col 9: valor           (ex: "R$ 60,00")
    col 10: obs            (tipo/categoria → products.description)
    col 11: tipo de venda  (ignorado)
    col 12: da onde eu conhece → customers.notes
"""

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, os.path.dirname(__file__))
from sqlalchemy import text
from app.core.database import SessionLocal

# ─── Caminhos padrão ────────────────────────────────────────────────────────
XLSX_PATH = os.path.join(os.path.dirname(__file__), "historico_pedidos.xlsx")
LOG_PATH  = os.path.join(os.path.dirname(__file__), "import_orders_log.txt")

# ─── Mapa manual de clientes ─────────────────────────────────────────────────
# Chave: fragmento do nome tal como aparece no XLSX (lowercase + sem acentos)
# Valor: nome EXATO que está no banco de dados
MAP_CLIENTES: dict[str, str] = {
    "naylessa":               "Naylessa",
    "eliana":                 "Eliana",
    "michelle":               "Michelle",
    "ana beatriz":            "Ana Beatriz",
    "katia":                  "Kátia",
    "cristina":               "Cristina Rodrigues",
    "giselda":                "Giselda",
    "juliana":                "Juliana",
    "carol":                  "Carol",
    "debora":                 "Débora",
    "maria fernanda":         "Maria Fernanda",
    "maria celia":            "Maria Célia",
    "simone":                 "Simone",
    "renata varella":         "Renata Varella",
    "renata varela":          "Renata Varela",
    "mae":                    "Mãe",
    "mae da maitê":           "Mônica mãe da Maitê",
    "monica mae da maite":    "Mônica mãe da Maitê",
    "alexandre":              "Alexandre",
    "thaís hartog":           "Thaís Hartog",
    "thais hartog":           "Thaís Hartog",
    "chefe fernanda":         "Chefe Fernanda",
    "chefe paula":            "Chefe Paula",
    "enzo":                   "Enzo",
    "irma da chefe fernanda": "Irmã da Chefe Fernanda",
    "irmã da chefe fernanda": "Irmã da Chefe Fernanda",
    "tatiane":                "Tatiane",
    "lulu":                   "Lulu",
    "graziela":               "Graziela",
    "michele":                "Michele",
    "miguel":                 "Miguel",
    "giselle":                "Giselle",
    "dani britto":            "Dani Britto",
    "dani brito":             "Dani Brito",
    "roseli":                 "Roseli",
    "claudia brazao":         "Claudia Brazão",
    "regimara":               "Regimara",
    "ana paula mattos":       "Ana Paula Mattos",
    "jussara murilo":         "Jussara (Murilo)",
    "jussara mae":            "Jussara (mãe)",
    "jussara":                "Jussara",
    "celia renara":           "Célia Renara",
    "lourdes":                "Lourdes",
    "ana cecilia":            "Ana Cecília",
    "karina":                 "Karina",
    "luciana cunha":          "Luciana Cunha",
    "paola":                  "Paola",
    "gilmara":                "Gilmara",
    "bia luciana":            "Bia Luciana",
    "luciana e adriana":      "Luciana e Adriana",
    "adriana":                "Adriana",
    "raquel":                 "Raquel",
    "roseana e mariana":      "Roseana e Mariana",
    "caroline":               "Caroline",
    "alessandra cossio":      "Alessandra Cóssio",
    "carla":                  "Carla",
    "janaina":                "Janaína",
    "andrea":                 "Andréa",
    "renatavarela":           "Renata Varela",
    "carol escobar":          "Carol",
    "meire":                  "Rosemeire",
    "sheila":                 "Sheila",
    "porchat":                "Karen Porchat",
    "tnia":                   "Tânia Luz",
    "vivi":                   "Viviane Macedo",
    "denise":                 "Denise",
    "karina gabao":           "Karina",
    "wnia":                   "Wânia",
    "laura":                  "Laura",
    "yasmin":                 "Yasmin",
    "janaina alberto":        "Janaína",
    "liege":                  "Liege",
    "cibele":                 "Cibele",
    "glauciane":              "Glauciane",
    "bete":                   "Bete",
    "fernanda hunold":        "Fernanda Camarano",
    "samatha barbosa":        "Samantha",
    "litz araujo":            "Litz",
    "rhuama":                 "Rhuama",
    "ivone":                  "Ivone",
    "luiz maneira pai":       "Luiz Antonio pai",
    "regina helena":          "Regina Helena",
    "juliana porto":          "Juliana Porto",
    "regimara":               "Regimara",
    "roseli":                 "Roseli",
    "giselle":                "Giselle",
}

# ─── Mapa manual de produtos ──────────────────────────────────────────────────
MAP_PRODUTOS: dict[str, str] = {
    # ── Princesas / Frozen ────────────────────────────────────────────────────
    "elsa":                                        "Elsa",
    "anna":                                        "Anna",
    "ana":                                         "Anna",
    "olaf":                                        "Olaf",
    "branca de neve":                              "Branca de Neve",
    "cinderela":                                   "Cinderella",
    "cinderella":                                  "Cinderella",
    "bella":                                       "Bela",
    "bela":                                        "Bela",
    "aurora":                                      "Aurora",
    "rapunzel":                                    "Rapunzel",
    "tiana":                                       "Tiana",
    "fiona":                                       "Fiona",
    "anastacia":                                   "Anastácia",
    "anastácia":                                   "Anastácia",
    "jasmine":                                     "Jasmine",
    "ariel":                                       "Ariel",
    "ariel sereia":                                "Ariel",
    "sofia":                                       "Sofia",
    "sininho":                                     "Sininho",
    "mulan":                                       "Mulan",
    "alice":                                       "Alice",
    "rainha de copas":                             "Rainha de Copas",
    "chapeleiro":                                  "Chapeleiro",
    "gato que ri":                                 "Gato que ri",
    "coelho branco":                               "Coelho Branco",
    "valente":                                     "Valente",
    "moana":                                       "Moana",
    "mirabel":                                     "Encanto Maribel Madrigal",
    "encanto maribel":                             "Encanto Maribel Madrigal",
    "maribel":                                     "Encanto Maribel Madrigal",
    "encanto isabela":                             "Encanto Isabela Madrigal",
    "encanto luiza":                               "Encanto Luíza Madrigal",
    "encanto dolores":                             "Encanto Dolores Madrigal",
    "encanto antonio":                             "Encanto Antônio Madrigal",
    "encanto bruno":                               "Encanto Bruno Madrigal",
    "encanto vela":                                "Encanto vela",
    # ── Super-heróis / Vilões ─────────────────────────────────────────────────
    "malévola":                                    "Malévola",
    "malevola":                                    "Malévola",
    "malevolas":                                   "Malévola",
    "malévolas":                                   "Malévola",
    "bruxa ma":                                    "Malévola",
    "bruxa má":                                    "Malévola",
    "rainha ma":                                   "Rainha Má",
    "rainha má":                                   "Rainha Má",
    "hulk":                                        "Hulk",
    "homem aranha":                                "Homem Aranha",
    "homem de ferro":                              "Homem de Ferro",
    "thor":                                        "Thor",
    "loki":                                        "Loki",
    "batman":                                      "Batman",
    "superman":                                    "Super Man",
    "super man":                                   "Super Man",
    "wolverine":                                   "Wolverine",
    "mulher maravilha":                            "Mulher Maravilha",
    "mulher gato":                                 "Mulher Gato",
    "capitao america":                             "Capitão América",
    "capitão america":                             "Capitão América",
    "capitão américa":                             "Capitão América",
    "principe bn":                                 "Príncipe Branca de Neve",
    "principe branca de neve":                     "Príncipe Branca de Neve",
    "pequeno principe":                            "Pequeno Príncipe",
    "pequeno príncipe":                            "Pequeno Príncipe",
    "madrasta":                                    "Madrasta",
    "lady bug":                                    "Lady Bug",
    "ladybug":                                     "Lady Bug",
    "catnoir":                                     "Catnoir",
    "buzz":                                        "Buzz",
    "woody":                                       "Woody",
    "chucky":                                      "Chucky",
    "yoda":                                        "Yoda",
    "darth vaider":                                "Darth Vaider",
    "darth vader":                                 "Darth Vaider",
    "chewbaca":                                    "Chewbaca",
    # ── Filmes / Personagens ──────────────────────────────────────────────────
    "shrek":                                       "Shrek",
    "fiona":                                       "Fiona",
    "bebês shrek":                                 "bebês Shrek",
    "bebes shrek":                                 "bebês Shrek",
    "mini shrek":                                  "Shrek",
    "ginger":                                      "Ginger",
    "mini ginger":                                 "Ginger",
    "masha":                                       "Masha",
    "urso":                                        "Urso",
    "baloo":                                       "Baloo",
    "mogli":                                       "Mogli",
    "jack sparol":                                 "Jack Sparol",
    "indiana jones":                               "Indiana Jones",
    "james bond":                                  "James Bond",
    "dorothy":                                     "Dorothy",
    "harry potter":                                "Harry Potter",
    "hermione":                                    "Hermione",
    "rony weasley":                                "Rony Weasley",
    "luna":                                        "Luna",
    "dumbledore":                                  "Dumbledore",
    "hagrid":                                      "Hagrid",
    "draco malfoy":                                "Draco Malfoy",
    "snape":                                       "Snape",
    "pikachu":                                     "Pikachu",
    "ash":                                         "Ash",
    "minion":                                      "Minion",
    "desprezível":                                 "Minion",
    "roger rabbit":                                "Roger Rabbit",
    "mary poppins":                                "Mary Poppins",
    "chaplin":                                     "Chaplin",
    "marilyn":                                     "Marilyn",
    "frida":                                       "Frida",
    "peter pan":                                   "Peter Pan",
    "capitao gancho":                              "Capitão Gancho",
    "capitão gancho":                              "Capitão Gancho",
    "lilo":                                        "Lilo",
    "stitch":                                      "Stitch",
    "lucy snoopy":                                 "Lucy - Snoopy",
    "boneca lucy snoopy":                          "Lucy - Snoopy",
    "lucy":                                        "Lucy - Snoopy",
    "snoopy":                                      "Lucy - Snoopy",
    "fred mercury personalizado":                  "Personalizada",
    "fred mercury - personalizado":                "Personalizada",
    "luan santana personalizado":                  "Personalizada",
    "luan santana - personalizado":                "Personalizada",
    "caio castro":                                 "Personalizada",
    "oscar oasis":                                 "Personalizada",
    "oscar oásis":                                 "Personalizada",
    "omulu":                                       "Personalizada",
    "amelie polan":                                "Boneca de pano",
    "mib":                                         "MIB",
    "chapolim":                                    "Chapolim",
    "chiquinha":                                   "Chiquinha",
    "chapeuzinho vermelho":                        "Chapeuzinho Vermelho",
    "lobo mau":                                    "Lobo mau",
    "vovo":                                        "Vovó",
    "vovó":                                        "Vovó",
    "cacador":                                     "Caçador",
    "caçador":                                     "Caçador",
    "dora":                                        "Dora",
    "diego":                                       "Diego",
    "galinha pintadinha":                          "Galinha Pintadinha",
    "bita":                                        "Bita",
    "patati":                                      "Patati",
    "patata":                                      "Patatá",
    "patatá":                                      "Patatá",
    "angry birds":                                 "Angry Birds",
    "minecraft":                                   "Minecraft",
    "bonecos roblox":                              "Bonecos Timart Natal",
    "roblox":                                      "Personagens Timart",
    # ── Bonecas Julie e variantes ─────────────────────────────────────────────
    "boneca julie":                                "Boneca Julie",
    "bonecos julie":                               "Boneca Julie",
    "julie":                                       "Boneca Julie",
    "familia julie":                               "Boneca Julie",
    "familia juli":                                "Boneca Julie",
    "bonecos julie negros":                        "Boneca Julie",
    "boneca julie negra":                          "Boneca Julie",
    "boneca julie negros":                         "Boneca Julie",
    "bonecos julie negros - casal":                "Boneca Julie",
    "casal bonecos julie pardo":                   "Boneca Julie",
    "casal bonecos julie juninos":                 "Boneca Julie",
    "casal de bonecos negros juli":                "Boneca Julie",
    "bonecos julie familia indigena":              "Boneca Julie",
    "bonecos julie familia indígena":              "Boneca Julie",
    "bonecos julie caipiras":                      "Boneca Julie",
    "familia negra com muda de roupa":             "Boneca Julie",
    "família negra com muda de roupa":             "Boneca Julie",
    "familia japonesa com muda de roupa":          "Boneca Julie",
    "família japonesa com muda de roupa":          "Boneca Julie",
    "familia branca com muda de roupa":            "Boneca Julie",
    "família branca com muda de roupa":            "Boneca Julie",
    "familia parda com muda de roupa":             "Boneca Julie",
    "família parda com muda de roupa":             "Boneca Julie",
    "mudas de roupa":                              "Boneca Julie",
    "julie de frida":                              "Boneca Julie",
    "casal junino":                                "Boneca Julie",
    "casal indio":                                 "Boneca Julie",
    "casal índio":                                 "Boneca Julie",
    "casal negro":                                 "Boneca Julie",
    "casal ruivo":                                 "Boneca Julie",
    "casal japones":                               "Boneca Julie",
    "casal japonês":                               "Boneca Julie",
    "bonecos nordestinos personalizados":          "Boneca de pano",
    "bonecos roqueiros personalizados":            "Boneca de pano",
    # ── Outras bonecas ────────────────────────────────────────────────────────
    "boneca cacau":                                "Boneca Cacau",
    "boneca cacau pretinha":                       "Boneca Cacau",
    "cacau":                                       "Boneca Cacau",
    "boneca waldorf":                              "boneca Waldorf",
    "waldorf":                                     "boneca Waldorf",
    "boneca negra":                                "boneca negra",
    "preta":                                       "boneca negra",
    "boneca emilia":                               "Boneca Emília",
    "boneca emília":                               "Boneca Emília",
    "boneca my":                                   "Boneca My",
    "coelhinha my":                                "Coelhinha My",
    "boneca my - so a boneca":                     "Boneca My",
    "boneca my so a boneca":                       "Boneca My",
    "lol":                                         "Boneca Lol Unicórnio",
    "sereia":                                      "Sereia de pano",
    "sereia de pano":                              "Sereia de pano",
    "sereiapano":                                  "Sereia de pano",
    "boneca de pano":                              "Boneca de pano",
    "boneca feltro personalizada":                 "Personalizada",
    "boneca personalizada":                        "Personalizada",
    "boneca gravidinha":                           "Boneca gravidinha",
    "bebes engatinhando personalizado":            "Personalizada",
    "bebês engatinhando - personalizado":          "Personalizada",
    "boneco personalizado homem-cao":              "Personalizada",
    "boneco personalizado homem-cão":              "Personalizada",
    "boneca zenobia":                              "Boneca Zen",
    "boneca zen":                                  "Boneca Zen",
    "boneca tata":                                 "Boneca Tatá",
    "boneca tatá":                                 "Boneca Tatá",
    "boneca malu":                                 "Boneca Malu",
    "boneca tilda":                                "Boneca Tilda",
    "boneca esperanca":                            "boneca Esperança",
    "boneca esperança":                            "boneca Esperança",
    "boneca musa do verao":                        "Boneca musa do verão",
    "boneca musa do verão":                        "Boneca musa do verão",
    "boneca mia":                                  "Boneca Mia",
    "bonequinha de luxo":                          "Bonequinha de luxo",
    # ── Escoteiro / Up ───────────────────────────────────────────────────────
    "escoteiro up":                                "Russel up",
    "russel up":                                   "Russel up",
    "sr.friederichesen":                           "Sr.Friederichesen",
    "sr friederichesen":                           "Sr.Friederichesen",
    # ── Castelo / Acessórios ──────────────────────────────────────────────────
    "castelo":                                     "Castelo",
    "personalizado":                               "Personalizado",
    "personalizada":                               "Personalizada",
    "casal personalizado":                         "Personalizado",
    "perso- nalizada":                             "Personalizada",
    "personalizado pq por favor":                  "Personalizada",
    "personalizado pq por favor azul":             "Personalizada",
    "personalizado feltro capoeira":               "Personalizada",
    # ── Peppa Pig ─────────────────────────────────────────────────────────────
    "peppa pig":                                   "Peppa Pig",
    "peppa":                                       "Peppa Pig",
    "familia peppa":                               "Peppa Pig",
    "irmao peppa pig":                             "irmão Peppa Pig",
    "irmão peppa pig":                             "irmão Peppa Pig",
    "mae da peppa":                                "Mãe da Peppa",
    "mãe da peppa":                                "Mãe da Peppa",
    "pai da peppa":                                "Pai da Peppa",
    # ── Tartaruga Ninja ───────────────────────────────────────────────────────
    "casco":                                       "Casco de Tartaruga Ninja",
    "casco tartaruga ninja":                       "Casco de Tartaruga Ninja",
    "tartaruga ninja":                             "Casco de Tartaruga Ninja",
    "mascara tartaruga":                           "Máscara de Tartaruga Ninja",
    "mascara tartaruga ninja":                     "Máscara de Tartaruga Ninja",
    "tartaruga":                                   "Tartaruga",
    # ── Presépio ─────────────────────────────────────────────────────────────
    "presepio":                                    "Presépio",
    "presepío":                                    "Presépio",
    "presépio":                                    "Presépio",
    "painel presepío":                             "Painel presépio",
    "painel presépio":                             "Painel presépio",
    "painel senninha":                             "Painel presépio",
    "tronco":                                      "Painel presépio",
    # ── Quadro de chamada ────────────────────────────────────────────────────
    "quadro de chamada":                           "Quadro de Chamada",
    "chamada":                                     "Quadro de Chamada",
    "chamadinha":                                  "Quadro de Chamada",
    "painel de chamada":                           "Quadro de Chamada",
    "chamadinha borboletas":                       "Quadro de Chamada",
    # ── Ponteiras ────────────────────────────────────────────────────────────
    "ponteiras de lapis":                          "Ponteira de lápis",
    "ponteiras de lápis":                          "Ponteira de lápis",
    "ponteira":                                    "Ponteira de lápis",
    # ── Marie ─────────────────────────────────────────────────────────────────
    "marie":                                       "Marie",
    "maries":                                      "Marie",
    # ── Bailarina ────────────────────────────────────────────────────────────
    "bailarina":                                   "Bailarina",
    # ── Fada ──────────────────────────────────────────────────────────────────
    "fada":                                        "Fadas",
    "fadas":                                       "Fadas",
    "fada branca":                                 "Fada Branca",
    # ── Palhaços ─────────────────────────────────────────────────────────────
    "palhacos":                                    "Palhaços",
    "palhaco":                                     "Palhaços",
    "palhaços":                                    "Palhaços",
    # ── Móbiles (todos viram "Móbile diverso" ou variante existente) ──────────
    "mobile":                                      "Móbile diverso",
    "mobiles":                                     "Móbile diverso",
    "móbile":                                      "Móbile diverso",
    "móbiles":                                     "Móbile diverso",
    "mobiles alfabeto e brinquedos":               "Móbile diverso",
    "mobiles bruxa":                               "Móbile de bruxa",
    "mobile de bruxa":                             "Móbile de bruxa",
    "mobiles menino maluquinho":                   "Móbile diverso",
    "móbiles menino maluquinho":                   "Móbile diverso",
    "mobiles do caso do bolinho":                  "Móbile diverso",
    "móbiles do caso do bolinho":                  "Móbile diverso",
    "mobiles alfabeto":                            "Móbile diverso",
    "mobiles sitio":                               "Móbile diverso",
    "móbiles sítio":                               "Móbile diverso",
    "mobiles historias":                           "Móbile diverso",
    "móbile histórias":                            "Móbile diverso",
    "mobiles de foguetes":                         "Móbile diverso",
    "móbiles de foguetes":                         "Móbile diverso",
    "mobile de animais":                           "Móbile diverso",
    "móbile de animais":                           "Móbile diverso",
    "mobile safari":                               "Móbile diverso",
    "móbile safari":                               "Móbile diverso",
    "mobile musical disney":                       "Móbile diverso",
    "móbile musical disney":                       "Móbile diverso",
    # ── Alfabeto ─────────────────────────────────────────────────────────────
    "alfabeto com botoes":                         "Alfabeto",
    "alfabeto":                                    "Alfabeto",
    "sr. alfabeto":                                "Sr. Alfabeto",
    "sr alfabeto":                                 "Sr. Alfabeto",
    "sra numeral":                                 "Sra Numeral",
    # ── Guirlanda ────────────────────────────────────────────────────────────
    "guirlanda de corujas":                        "Guirlanda de corujas",
    "guirlanda corujas":                           "Guirlanda de corujas",
    "guirlanda":                                   "Guirlanda de corujas",
    "guirlanda personalizada":                     "guirlanda personalizada",
    "mini guirlanda":                              "mini guirlanda",
    "guirlanda de rolha":                          "guirlanda de rolha",
    "guirlanda sagrada familia":                   "Guirlanda sagrada Família",
    "guirlanda lar doce lar":                      "Guirlanda Lar doce lar",
    "guirlanda passarinhos":                       "Guirlanda Passarinhos",
    "guirlanda noel praia":                        "Guirlanda Noel praia",
    "guirlanda de animais marinhos":               "Guirlanda de corujas",
    # ── Papai Noel ───────────────────────────────────────────────────────────
    "papai noel espiralado":                       "Papai Noel espiralado",
    "papais noel espiralado":                      "Papai Noel espiralado",
    "papai noel espiraado":                        "Papai Noel espiralado",
    "papai noel boneco":                           "Papai Noel boneco",
    "papai noel calendario":                       "Papai Noel calendário",
    "papai noel surfista":                         "papai Noel surfista",
    "papai noel na lua":                           "Papai Noel na Lua",
    "papai noel de pijama":                        "Papai Noel de pijama",
    "mamae noel de pijama":                        "Mamãe Noel de pijama",
    "papai noel macaeta de porta":                 "Papai Noel maçaneta de porta",
    "papai noel macaneta de porta":                "Papai Noel maçaneta de porta",
    # ── Buquê ─────────────────────────────────────────────────────────────────
    "buque de santo antonio":                      "buquê Santo Antônio",
    "buquê de santo antonio":                      "buquê Santo Antônio",
    "buque sao jose":                              "buquê São José",
    "buquê são josé":                              "buquê São José",
    "buque cupido":                                "buquê Cupido",
    "buque sapo":                                  "Buquê sapo",
    "buque pinguim":                               "buquê Pinguim",
    "buque de rosas":                              "Buquê de rosas",
    "buquê de rosas":                              "Buquê de rosas",
    # ── Conserto / Restauro ───────────────────────────────────────────────────
    "restauro de boneca":                          "Conserto",
    "restauro":                                    "Conserto",
    "conserto":                                    "Conserto",
    "manutencoes":                                 "Conserto",
    "manutenções":                                 "Conserto",
    # ── Dedoches ─────────────────────────────────────────────────────────────
    "dedoche":                                     "Dedoches coelhinho",
    "dedoches":                                    "Dedoches coelhinho",
    "dedoches coelhinho":                          "Dedoches coelhinho",
    "dedoches passaarinho personalizado":          "Dedoches passaarinho personalizado",
    "kit 4 dedoches animais":                      "kit 4 dedoches animais",
    "kit dedoches do alfabeto":                    "kit dedoches do alfabeto",
    "fantoches - menina e menino":                 "Fantoches de fralda",
    "fantoches de fralda":                         "Fantoches de fralda",
    "fantoche caracol":                            "Fantoche Caracol",
    "fantoche tartaruga":                          "Fantoche Tartaruga",
    "fantoche personalizado":                      "Fantoche personalizado",
    "fantoche canarinho pistola":                  "Fantoche canarinho pistola",
    "fantoche mascote qatar":                      "Fantoche mascote Qatar",
    "fantoche peixinho virtuoso":                  "Fantoche peixinho virtuoso",
    "fantoche coelho lado":                        "fantoche coelho lado",
    # ── Árvore ───────────────────────────────────────────────────────────────
    "arvore":                                      "Árvore de feltro de parede",
    "arvores":                                     "Árvore de feltro de parede",
    "árvores":                                     "Árvore de feltro de parede",
    "arvore de parede":                            "Árvore de feltro de parede",
    "arvore com girassol":                         "Árvore de feltro de parede",
    "árvore com girassol na ponta":                "Árvore de feltro de parede",
    "arvore com girassol na ponta":                "Árvore de feltro de parede",
    "arvore de feltro de parede":                  "Árvore de feltro de parede",
    "arvore de feltro chao":                       "Árvore de feltro chão",
    "árvore de feltro chão":                       "Árvore de feltro chão",
    "enfeites de arvore":                          "Enfeite de Natal",
    "enfeites de árvor":                           "Enfeite de Natal",
    "enfeites de arvore mickey":                   "Enfeite de Natal Mickey",
    "enfeites de árvore mickey":                   "Enfeite de Natal Mickey",
    "dentes para arvore":                          "Guirlanda dentes",
    "dentes para árvor":                           "Guirlanda dentes",
    "dentes para árvore":                          "Guirlanda dentes",
    "papai noel atravessado na arvore":            "Enfeite de Natal",
    "papai noel atravessado na árvor":             "Enfeite de Natal",
    "arvore de natal 3d":                          "Árvore de Natal 3D",
    "arvore de natal com gatinho e luz":           "Árvore de Natal com gatinho e luz",
    "enfeite de natal":                            "Enfeite de Natal",
    "enfeites de natal do estranho mundo de jack": "Enfeite de Natal",
    "enfeites senti- mentos":                      "enfeite de natal sentimentos",
    "enfeites sentimentos":                        "enfeite de natal sentimentos",
    "enfeite de natal sentimentos":                "enfeite de natal sentimentos",
    "potes natal":                                 "Rótulos para pote de vidro Natal",
    "pingente mickey":                             "Chaveiros Mickey",
    "luvas mickey":                                "luva indiozinho",
    "luva mickey":                                 "luva indiozinho",
    "jack cabeça e punhos para arvore natal":      "Jack - cabeça e punhos para árvore Natal",
    "jack - cabeça e punhos para arvore natal":    "Jack - cabeça e punhos para árvore Natal",
    "jack cabeça e punhos para árvore natal":      "Jack - cabeça e punhos para árvore Natal",
    "enfeite de porta noel chamine":               "Enfeite de porta Noel chaminé",
    "enfeite de porta noel surfista pq":           "Enfeite de porta Noel surfista pq",
    "enfeite de porta rena":                       "Enfeite de porta Rena",
    "enfeite de porta noel boia":                  "Enfeite de porta Noel bóia",
    "porta talher noel":                           "Porta talher Noel",
    "tampa de vaso noel":                          "Capa de vaso sanitário",
    "capa de vaso sanitario":                      "Capa de vaso sanitário",
    "botas de natal personalizada":                "Botas de Natal personalizada",
    "botas":                                       "Botas",
    "bota de salto de natal":                      "Bota de salto de Natal",
    "porta papel higienico noel":                  "Porta papel higiênico Noel",
    "pinheirinho de alinhavo":                     "Pinheirinho de alinhavo",
    "casinha natal":                               "Casinha Natal",
    "bonecos timart natal":                        "Bonecos Timart Natal",
    "rena com roupa":                              "Enfeite de porta Rena",
    "rena natal":                                  "Rena Natal",
    "enfeite porta placas natal":                  "Enfeite porta placas Natal",
    "noel bag":                                    "Noel Bag",
    "sacolas seinf":                               "Sacolas Seinf",
    "calendario do advento":                       "Calendário do Advento",
    "pinheirinho para foto":                       "Pinheirinho para foto",
    # ── Feirinha ─────────────────────────────────────────────────────────────
    "feirinha":                                    "Feirinha de feltro",
    "feirinha de feltro":                          "Feirinha de feltro",
    "feirinhas":                                   "Feirinha de feltro",
    # ── Jacaré ────────────────────────────────────────────────────────────────
    "jacare":                                      "Jacaré Joca",
    "jacaré":                                      "Jacaré Joca",
    "jacare joca":                                 "Jacaré Joca",
    "jacaré joca":                                 "Jacaré Joca",
    "joca":                                        "Jacaré Joca",
    "jacare timart grande":                        "Jacaré Timart grande",
    "jacaré timart grande":                        "Jacaré Timart grande",
    # ── Gato ──────────────────────────────────────────────────────────────────
    "gato preto":                                  "Gato preto",
    "gato":                                        "Gato preto",
    "gatinhos":                                    "Gatinhos",
    "gatinhos tecido":                             "Gatinhos tecido",
    "gatinho preto anjinho":                       "Pet anjinho",
    "gato na caixa":                               "Gato na caixa",
    "gato xadrez":                                 "Gato xadrez",
    "naninha gato":                                "Naninhas e seus filhotes",
    "naninha raposa":                              "Naninhas e seus filhotes",
    "naninhas e seus filhotes":                    "Naninhas e seus filhotes",
    # ── Moto ──────────────────────────────────────────────────────────────────
    "moto":                                        "Moto",
    # ── Cachorrinho ──────────────────────────────────────────────────────────
    "cachorrinho":                                 "Cachorrinho de argolas",
    "cachorrinho com paninho":                     "Cachorrinho de argolas",
    "paninho com cabeça de urso":                  "Paninho com cabeça de urso",
    "kit cachorrinho":                             "Estrelinhas cachorrinhos",
    "kit cachor- rinhos":                          "Estrelinhas cachorrinhos",
    "cachorrinhos timart":                         "Cachorrinhos Timart",
    "estrelinhas cachorrinhos":                    "Estrelinhas cachorrinhos",
    "estrelinhas gatinhos":                        "Estrelinhas gatinhos",
    # ── Galo / Porco / Animais ────────────────────────────────────────────────
    "galo":                                        "Galo da Moana",
    "porco":                                       "Porquinho",
    "porquinho":                                   "Porquinho",
    "pua porquinho da moana":                      "Puá porquinho da Moana",
    "sapo":                                        "Sapo da Hello Kity",
    "rato":                                        "Personagens Timart",
    "cobra":                                       "Personagens Timart",
    "cachorro":                                    "Cachorrinho de argolas",
    "pato":                                        "Patinho colorido",
    "patinho":                                     "Patinho colorido",
    "lenhador":                                    "Boneco Tutu",
    "macacos sem rabo":                            "Personagens Timart",
    "macaco":                                      "Personagens Timart",
    "onca":                                        "Onça",
    "onça":                                        "Onça",
    "peixe":                                       "peixe",
    "baiacu":                                      "Baiacu",
    # ── Fundo do mar ─────────────────────────────────────────────────────────
    "kit fundo do mar":                            "Pescaria de ímã",
    "pescaria de animais marinhos":                "Pescaria de ímã",
    "pescaria de ima":                             "Pescaria de ímã",
    "pescaria de ímã":                             "Pescaria de ímã",
    "polvo grande":                                "Polvo grande",
    "polvinho do humor":                           "Polvinho do humor",
    "peixe grande":                                "Peixe grande",
    "baleia":                                      "Baleia",
    "tubarao":                                     "Tubarão",
    "tubarão":                                     "Tubarão",
    "agua viva":                                   "Água Viva",
    "água viva":                                   "Água Viva",
    "lula":                                        "Lula",
    "estrela do mar":                              "Estrela do mar",
    "concha":                                      "Concha",
    "mergulhador":                                 "Mergulhador",
    "mergulhadora":                                "Mergulhadora",
    "cavalo marinho":                              "Cavalo Marinho",
    "arraia":                                      "Arraia",
    "algas":                                       "Algas",
    "caranguejo":                                  "Caranguejo",
    "bichinhos do mar pequenos":                   "Bichinhos do mar pequenos",
    # ── Corujinhas ───────────────────────────────────────────────────────────
    "corujinhas":                                  "Corujinhas Natal com ventosa",
    "corujinhas de natal":                         "Corujinhas Natal com ventosa",
    "corujas arvore peso de porta":                "Coruja árvore",
    "corujas árvore peso de porta":                "Coruja árvore",
    "coruja arvore":                               "Coruja árvore",
    "coruja árvore":                               "Coruja árvore",
    "marcadores coruja":                           "Marcadores Coruja",
    # ── Chaveiros ────────────────────────────────────────────────────────────
    "chaveiro":                                    "Chaveiro",
    "chaveiros":                                   "Chaveiro",
    "chaveiro coruja":                             "Chaveiro Coruja",
    "chaveiro flork":                              "Chaveiro Flork",
    "chaveiros mickey":                            "Chaveiros Mickey",
    "chaveiros frozen":                            "Chaveiros Frozen",
    "chaveiro mario":                              "Chaveiro Mário",
    "chaveiro nemo":                               "Chaveiro Nemo",
    "chaveiro yellowfant":                         "Chaveiro Yellowfant",
    "chaveiros personalizados":                    "Chaveiro",
    "chaveiros de flores na la":                   "Chaveiro",
    "chaveiros ovelhinhas":                        "Chaveiro",
    "chaveiros cachorro personalizado":            "Chaveiro",
    "ursinhas pingentes":                          "Ursinhas para árvore de Natal",
    "pingente cara noel":                          "Pingente cara Noel",
    "pingente dente":                              "pingente dente",
    "pingente panda":                              "Pingente Panda",
    "enfeite de natal pingente":                   "Enfeite de Natal pingente",
    # ── Almofadas ────────────────────────────────────────────────────────────
    "almofada unicornio":                          "Almofadinha piquet",
    "almofadinha":                                 "Almofadinha piquet",
    "almofada foguete quadrada":                   "almofadas",
    "almofadas":                                   "almofadas",
    "almofada rolinho":                            "Travesseirinho",
    "rolinhos almofada":                           "Travesseirinho",
    "travesseirinho":                              "Travesseirinho",
    "almofada jacare":                             "Almofada Jacaré",
    "almofada jacaré":                             "Almofada Jacaré",
    # ── Capas / papelaria ─────────────────────────────────────────────────────
    "capa de diario":                              "Capa de diário",
    "capa de diário":                              "Capa de diário",
    "capa de caderno":                             "Capa de diário",
    "capas de caderno":                            "Capa de diário",
    "capas de biblia":                             "Capa de diário",
    "capas de bíblia":                             "Capa de diário",
    "folhas adesivadas/plastificadas":             "Papelaria - impressão e plastificação",
    "folhas adesivas / plastificadas":             "Papelaria - impressão e plastificação",
    "folhas adesivas":                             "Papelaria - impressão e plastificação",
    "folha adesiva":                               "Papelaria - impressão e plastificação",
    "folhas plastificadas":                        "Papelaria - impressão e plastificação",
    "folhas papelaria":                            "Papelaria - impressão e plastificação",
    "folhas de papelaria":                         "Papelaria - impressão e plastificação",
    "plastificacoes pequenas":                     "Papelaria - impressão e plastificação",
    "plastificações pequenas":                     "Papelaria - impressão e plastificação",
    "paginas plastificadas de rotina":             "Papelaria - impressão e plastificação",
    "páginas plastificadas de rotina":             "Papelaria - impressão e plastificação",
    "encadernacao":                                "Encadernação",
    "encadernação":                                "Encadernação",
    "sacolinhas de pascoa":                        "Sacolinhas de Páscoa",
    "sacolinhas":                                  "Sacolinhas",
    "saquinhos de feltro":                         "Sacolinhas",
    "saquinhos para sache":                        "Sachês",
    "saquinhos para sachê":                        "Sachês",
    "saches":                                      "Sachês",
    "sachês":                                      "Sachês",
    "bodys com sache":                             "Body lembrancinha",
    "bodys com sachê":                             "Body lembrancinha",
    "body lembrancinha":                           "Body lembrancinha",
    "caixinhas lembrancinha":                      "Caixinhas lembrancinha",
    "caixinha de feltro pascoa":                   "caixinha de feltro páscoa",
    "ovos embalagens":                             "Embalagem de ovos de Páscoa",
    "embalagem de ovos de pascoa":                 "Embalagem de ovos de Páscoa",
    # ── Pintura / Ecobag ─────────────────────────────────────────────────────
    "pintura em camiseta":                         "Pintura na ecobag",
    "pinturas em camisetas":                       "Pintura na ecobag",
    "pinturas de camisetas":                       "Pintura na ecobag",
    "pintura de camiseta":                         "Pintura na ecobag",
    "pintura na ecobag":                           "Pintura na ecobag",
    "camisetas pintadas com fras":                 "Pintura na ecobag",
    # ── Insetos / Bichos ─────────────────────────────────────────────────────
    "grilo":                                       "Insetos feltro",
    "formiga":                                     "Insetos feltro",
    "insetos":                                     "Insetos feltro",
    "barata":                                      "Insetos feltro",
    "centopeia":                                   "Centopéia",
    "centopéia":                                   "Centopéia",
    "minhoca":                                     "Centopéia",
    "minhoco":                                     "Centopéia",
    # ── Boneco Tutu ──────────────────────────────────────────────────────────
    "carpinteiro":                                 "Boneco Tutu",
    "boneco tutu":                                 "Boneco Tutu",
    # ── Puffys ───────────────────────────────────────────────────────────────
    "kits de puffys noel":                         "Puffys Noel",
    "puffys noel":                                 "Puffys Noel",
    "kit de puffy noel":                           "Puffys Noel",
    "kit puffy noel":                              "Puffys Noel",
    "kits de puffy alice":                         "Puffys Alice",
    "puffys alice":                                "Puffys Alice",
    "puffys star wars":                            "Puffys Star Wars",
    "puffys harry potter":                         "Puffys Harry Potter",
    "puffys harry potter 2":                       "Puffys Harry Potter 2",
    "puffys presepío":                             "Puffys Presépio",
    "puffys presepio":                             "Puffys Presépio",
    "puffys presépio":                             "Puffys Presépio",
    "puffys personalizados":                       "Puffys personalizados",
    "puffys magico de oz":                         "Puffys Mágico de Oz",
    "puffys mágico de oz":                         "Puffys Mágico de Oz",
    "kit magico de oz":                            "Puffys Mágico de Oz",
    "kit mágico de oz":                            "Puffys Mágico de Oz",
    "puffys monstrinhos":                          "Puffys Monstrinhos",
    "puffys estrelinhas noel":                     "Puffys Noel",
    "puffys encanto":                              "Puffys Encanto",
    "puffys stitch":                               "Puffys Stitch",
    "puffys grinch":                               "Puffys Grinch",
    "puffys princesas":                            "Puffys Princesas",
    "puffys natal 2":                              "Puffys Natal 2",
    "kit noel":                                    "Puffys Noel",
    # ── Enfeites Mickey / Natal ──────────────────────────────────────────────
    "kits enfeite mickey":                         "Enfeite de Natal Mickey",
    "enfeite mickey":                              "Enfeite de Natal Mickey",
    "enfeite de natal mickey":                     "Enfeite de Natal Mickey",
    "enfeite de porta":                            "Enfeite de porta",
    "enfeite lar doce lar abelhas":                "Enfeite Lar doce Lar abelhas",
    "guirlanda coelho tecido":                     "Guirlanda Coelho tecido",
    "casinha do coelho cogumelo":                  "casinha do coelho cogumelo",
    "coelho porta barra de chocolate":             "Coelho porta barra de chocolate",
    "descanso de caneca coelhos":                  "descanso de caneca coelhos",
    "enfeite de porta pascoa coracao":             "enfeite de porta páscoa coração",
    "enfeite de porta pascoa":                     "Enfeite de porta de Páscoa",
    "enfeite de porta de pascoa":                  "Enfeite de porta de Páscoa",
    # ── Estrelas / Estrelinhas ───────────────────────────────────────────────
    "estrela de davi":                             "Estrela de Davi",
    "estrela":                                     "Estrela",
    "estrelinhas personalizadas":                  "Estrelinhas personalizadas",
    "estrelinhas pequeno principe":                "Estrelinhas Pequeno Príncipe",
    "estrelinhas copa do mundo":                   "Estrelinhas Copa do Mundo",
    "estrelinhas noel":                            "Estrelinhas Noel",
    # ── Marcadores ───────────────────────────────────────────────────────────
    "marcador de livro":                           "Marcador de livro Batman",
    "marcadores de pagina":                        "Marcador de livro Batman",
    "marcadores de página":                        "Marcador de livro Batman",
    "marcadores de pagina mulher maravilha":       "Marcador de livro Batman",
    "marcador de livro elastico coruja":           "Marcador de livro elástico coruja",
    # ── Coelhos / Páscoa ─────────────────────────────────────────────────────
    "coelhas":                                     "Coelhas",
    "coelhos de pendurar no varal":                "Coelho de varal",
    "coelho de varal":                             "Coelho de varal",
    "coelho na cenoura":                           "Coelho na cenoura",
    "coelhinhos da timart":                        "Coelhinhos da Timart",
    "carneirinho pequena":                         "Sacola com 10 carneirinhos",
    "ovelha de 16cm":                              "Ovelha de pano",
    "ovelha de pano":                              "Ovelha de pano",
    "casal de ovelhinhas":                         "Casal de ovelhinhas",
    "fivelas de pascoa":                           "Fivelas de Páscoa",
    "fivelas de páscoa":                           "Fivelas de Páscoa",
    "cenouras de tecido":                          "Cenouras de tecido",
    "guirlanda de pascoa":                         "Guirlanda de Páscoa",
    "guirlanda de páscoa":                         "Guirlanda de Páscoa",
    "jogo acerte a cenoura":                       "jogo acerte a cenoura",
    "coelha laura":                                "Coelha Laura",
    "coelho equilibrista":                         "Coelho equilibrista",
    "quick book ovo de pascoa":                    "quiet book ovo de páscoa",
    "quiet book ovo de pascoa":                    "quiet book ovo de páscoa",
    "quiet book ovo de páscoa":                    "quiet book ovo de páscoa",
    "coelho coruja":                               "Coelho coruja",
    "coelhinhos baby":                             "Coelhinhos Baby",
    # ── Quiet Books ───────────────────────────────────────────────────────────
    "quiet book corujinha":                        "Quiet book Corujinha",
    "quiet book vies":                             "Quiet book viés",
    "quiet book viés":                             "Quiet book viés",
    "quiet book das frutas":                       "Quiet book das frutas",
    "mini quiet book":                             "Mini quiet book",
    "quiet book casinha de boneca":                "Quiet book Casinha de Boneca",
    "quiet book sereia":                           "Quiet book Sereia",
    "quiet book cogumelo":                         "Quiet book cogumelo",
    "quiet book pinguim":                          "Quiet book Pinguim",
    "quiet book animais baby":                     "Quiet book animais baby",
    "quiet book baby":                             "Quiet book baby",
    "quiet book a casa e seu dono":                "Quiet book A casa e seu dono",
    # ── Casal de Boneco de neve ───────────────────────────────────────────────
    "casal de boneco de neve":                     "Casal de boneco de neve",
    "bonecos de neve":                             "Casal de boneco de neve",
    # ── Tsum Tsum / Hello Kitty ──────────────────────────────────────────────
    "tsum tsum":                                   "Tsum tsum",
    "hello kity":                                  "Hello Kity",
    "hello kitty":                                 "Hello Kity",
    "my melody":                                   "My Melody",
    "sapo da hello kity":                          "Sapo da Hello Kity",
    # ── Kits especiais ────────────────────────────────────────────────────────
    "kit menininha com 3 roupas, mochila e bolsa":  "Boneca Julie",
    "kit menininha":                               "Boneca Julie",
    "kit 3 porquinhos":                            "Kit 3 porquinhos",
    "kit chapeuzinho painel":                      "kit Chapeuzinho painel",
    "kit porquinhos painel":                       "kit porquinhosn painel",
    "kit joao e maria painel":                     "kit João e Maria painel",
    "kit cachinhos dourados painel":               "kit Cachinhos Dourados painel",
    "kit frango assado":                           "kit frango assado",
    "kit panelinhas":                              "kit panelinhas",
    "kit mercadinho":                              "kit mercadinho",
    "kit cafe da manha":                           "kit café da manhã",
    "kit café da manhã":                           "kit café da manhã",
    "kit restaurante":                             "kit restaurante",
    "kit divertidament":                           "Puffys personalizados",
    "kit tapa olho":                               "Sacolinhas",
    # ── Bichinhos de caixinha ─────────────────────────────────────────────────
    "bichinhos de caixinha de musica":             "Personagens Caixa de música",
    "bichinhos de caixinha de música":             "Personagens Caixa de música",
    "personagens caixa de musica":                 "Personagens Caixa de música",
    # ── Tapetes / sensoriais ─────────────────────────────────────────────────
    "tapete sensorial":                            "tapetes",
    "tapetes":                                     "tapetes",
    "painel de texturas":                          "painel de texturas",
    "cards sensoriais":                            "Cards sensoriais",
    # ── Frutas de feltro ─────────────────────────────────────────────────────
    "meloes":                                      "Melão de feltro",
    "melões":                                      "Melão de feltro",
    "melao de feltro":                             "Melão de feltro",
    "melancias":                                   "Melancia de feltro",
    "melancia de feltro":                          "Melancia de feltro",
    "aboboras":                                    "Abóbora de feltro",
    "abóboras":                                    "Abóbora de feltro",
    "abobora de feltro":                           "Abóbora de feltro",
    "frutas sensoriais":                           "Frutas sensoriais",
    "gomos de laranja":                            "Gomos de laranja",
    "kit frutinhas com rosto":                     "kit frutinhas com rosto",
    # ── Tornozeleiras / rolinhos ─────────────────────────────────────────────
    "tornozeleiras de arroz":                      "Sachês",
    "rolinhos almofada":                           "Travesseirinho",
    "rolinho":                                     "Travesseirinho",
    "rolinhos":                                    "Travesseirinho",
    # ── Outros itens ──────────────────────────────────────────────────────────
    "dona maricota":                               "Fantoches seu Lobato",
    "comissarios de bordo":                        "Boneca de pano",
    "comissários de bordo":                        "Boneca de pano",
    "filhos":                                      "Boneca Julie",
    "fusca herbi":                                 "Herbie",
    "herbie":                                      "Herbie",
    "fusca herbie":                                "Herbie",
    "de brind":                                    "Sacolinhas",
    "cega":                                        "Boneca de pano",
    "amputado":                                    "Boneca de pano",
    "menininha de avental de nutricionista":        "Personalizada",
    "princesas timart":                            "Personagens Timart",
    "bonecos viloes disney":                       "Bonecos feltro Vilões Disney",
    "bonecos feltro viloes disney":                "Bonecos feltro Vilões Disney",
    "amarradinho":                                 "Sacolinhas",
    "argolas de guardanapos":                      "Porta guardanapo flor",
    "porta guardanapo flor":                       "Porta guardanapo flor",
    "guardanapos de pano":                         "Guardanapos de pano",
    "placa de mesversario":                        "Placa de mesversário",
    "placa de mesversário":                        "Placa de mesversário",
    "coroa de mesversario":                        "Coroa de mesversário",
    "coroa de mesversário":                        "Coroa de mesversário",
    "saia de arvore personalizada":                "Saia de árvore personalizada",
    "saia de árvore personalizada":                "Saia de árvore personalizada",
    "memory bear":                                 "Memory bear",
    "cartaz aniversariantes":                      "Cartaz aniversariantes",
    "naninhas pintinho amarelinho":                "Naninhas Pintinho amarelinho",
    "naninhas pintinho":                           "Naninhas Pintinho amarelinho",
    "naninha pequeno principe":                    "Naninha Pequeno Príncipe",
    "naninha pequeno príncipe":                    "Naninha Pequeno Príncipe",
    "teatro de fantoches":                         "Teatro de fantoches",
    "fantoches seu lobato":                        "Fantoches seu Lobato",
    "pecinhas de um painel pronto":                "Pecinhas de um painel pronto",
    "bonecos julie negros casal":                  "Boneca Julie",
    "bobby goods":                                 "Bobby Goods",
    "mascara boitata":                             "Máscara Boitatá",
    "máscara boitatá":                             "Máscara Boitatá",
    "labubu":                                      "Labubu",
    "bastidor boneco de neve":                     "Bastidor boneco de neve",
    "bastidor noel":                               "Bastidor noel",
    "bastidor rena":                               "Bastidor rena",
    "paes":                                        "Pães",
    "pães":                                        "Pães",
    "kit dedoches do alfabeto":                    "kit dedoches do alfabeto",
    "bonequinhas de pernas e bracos trancadas":    "Bonequinhas de pernas e braços trançados",
    "bonequinhas de pernas e braços trançados":    "Bonequinhas de pernas e braços trançados",
    "painel para escovas de dente":                "Painel para escovas de dente",
    "orelhas tiara personalizada":                 "Orelhas tiara personalizada",
    "sacola":                                      "Sacola",
    "bolsa de chita":                              "Bolsa de chita",
    "bebe personalizada":                          "Personalizada",
    "bebe personalizado":                          "Personalizada",
    "rolinhos":                                    "Travesseirinho",
    "rolinhos 80x20cm":                            "Travesseirinho",
    "comissarios":                                 "Boneca de pano",
    "espírito santo de pendurar":                  "Espírito Santo de pendurar",
    "espirito santo de pendurar":                  "Espírito Santo de pendurar",
    "hipopotama":                                  "Hipopótama",
    "hipopótama":                                  "Hipopótama",
    "cavalo de fogo e a menina":                   "Cavalo de fogo e a menina",
    "cavalinho de pau":                            "Cavalinho de pau",
    "unicornio de pau":                            "Unicórnio de pau",
    "leaozinho":                                   "Leãozinho",
    "leãozinho":                                   "Leãozinho",
    "ourico contador":                             "Ouriço contador",
    "ouriço contador":                             "Ouriço contador",
    "lupa elefante":                               "Lupa elefante",
    "maleta casinha de boneca":                    "Maleta casinha de boneca",
    "maleta medica":                               "Maleta médica",
    "maleta médica":                               "Maleta médica",
    "bola sensorial":                              "Bola sensorial",
    "bola montessori":                             "Bola Montessori",
    "tangram":                                     "Tangram",
    "quebra-cabeça 3d dinossauros":                "Quebra-cabeça 3D dinossauros",
    "quebra cabeça 3d dinossauros":                "Quebra-cabeça 3D dinossauros",
    "relógio do clima":                            "Relógio do clima",
    "relogio do clima":                            "Relógio do clima",
    "menininhos e menininhas":                     "Menininhos e menininhas",
    "maozinha articulada":                         "Mãozinha articulada",
    "mãozinha articulada":                         "Mãozinha articulada",
    "casa sonolenta":                              "Casa Sonolenta",
    "livro bom dia todas as cores":                "Livro Bom dia todas as cores",
    "livro o cabelo de lele":                      "Livro O cabelo de Lelê",
    "livro o cabelo de lelê":                      "Livro O cabelo de Lelê",
    "caixa esquema corporal rosto":                "Caixa esquema corporal rosto",
}

# ─── Helpers de texto ─────────────────────────────────────────────────────────
def normalizar(texto: str) -> str:
    """Remove acentos, lowercase, espaços duplicados."""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def parse_date(raw) -> datetime | None:
    """Suporta vários formatos de data e objetos datetime do pandas."""
    # Valor vazio ou nulo
    if raw is None or raw == "":
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    # Já é datetime Python
    if isinstance(raw, datetime):
        return raw
    # Timestamp do pandas
    if hasattr(raw, "to_pydatetime"):
        return raw.to_pydatetime()
    # String
    s = str(raw).strip()
    if s in ("", "nan", "-", "calote - sem a entrega"):
        return None
    # Remove espaços internos para formatos dd/mm/aaaa
    s_compact = re.sub(r"\s+", "", s)
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s_compact, fmt)
        except ValueError:
            pass
    return None


def parse_value(raw) -> float:
    """Converte 'R$ 1.234,56' ou '350' → float."""
    if pd.isna(raw):
        return 0.0
    s = str(raw).strip()
    s = re.sub(r"[R$\s\xa0]", "", s)
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def extrair_produtos(desc: str) -> list[tuple[int, str]]:
    """
    Extrai lista de (quantidade, nome) de descrições como:
      '1 Elsa e 1 Anna'
      '2 Malévolas, 1 Aurora e 1 Fiona'
      '3 móbiles alfabeto e brinquedos'
    """
    desc = str(desc).strip()
    desc = re.sub(r"[\r\n]+", " ", desc)
    desc = re.sub(r"\s+", " ", desc)

    resultados: list[tuple[int, str]] = []

    # Padrão: número seguido de nome até próxima vírgula/conector/número
    padrao = re.findall(
        r"(\d+)\s+([^,\d\n]+?)(?=\s*[,]\s*\d|\s+e\s+\d|\s*$)",
        desc,
        re.IGNORECASE,
    )
    for qty_str, nome in padrao:
        nome = nome.strip().rstrip(" e").strip()
        if nome:
            resultados.append((int(qty_str), nome))

    # Fallback simples: "N nome"
    if not resultados:
        m = re.match(r"^(\d+)\s+(.+)$", desc)
        if m:
            resultados.append((int(m.group(1)), m.group(2).strip()))

    return resultados


# ─── Busca fuzzy ─────────────────────────────────────────────────────────────
FUZZY_THRESHOLD = 72   # pontuação mínima para aceitar um match fuzzy

def fuzzy_find(
    nome: str,
    mapa: dict[str, int],
    limiar: int = FUZZY_THRESHOLD,
) -> tuple[int | None, str | None, int]:
    """
    Busca em `mapa` {nome_normalizado: id} usando:
      1. match exato
      2. containment (um contém o outro)
      3. rapidfuzz token_sort_ratio
    Retorna (id, nome_encontrado, score) ou (None, None, 0).
    """
    if not nome or not mapa:
        return None, None, 0

    chave = normalizar(nome)

    # 1. exato
    if chave in mapa:
        return mapa[chave], chave, 100

    # 2. containment
    for k in mapa:
        if chave in k or k in chave:
            return mapa[k], k, 95

    # 3. rapidfuzz
    melhor = process.extractOne(
        chave, list(mapa.keys()), scorer=fuzz.token_sort_ratio
    )
    if melhor and melhor[1] >= limiar:
        return mapa[melhor[0]], melhor[0], melhor[1]

    return None, None, 0


# ─── CLI ─────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="Importa pedidos históricos do XLSX para o banco."
    )
    parser.add_argument(
        "--file", default=XLSX_PATH,
        help=f"Caminho do XLSX (padrão: {XLSX_PATH})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apenas mostra o que seria feito, sem gravar.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="APAGA todos os pedidos existentes antes de importar (cuidado!).",
    )
    parser.add_argument(
        "--fuzzy-threshold", type=int, default=FUZZY_THRESHOLD,
        help=f"Limiar mínimo de similaridade fuzzy (padrão: {FUZZY_THRESHOLD}).",
    )
    return parser.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()
    limiar = args.fuzzy_threshold

    if not os.path.exists(args.file):
        print(f"[ERRO] Arquivo não encontrado: {args.file}")
        sys.exit(1)

    # ── 1. Lê o XLSX ──────────────────────────────────────────────────────────
    print(f"[CSV] Lendo: {args.file}")
    df = pd.read_excel(args.file, header=None, engine="openpyxl")
    df = df.fillna("")

    pedidos: list[dict] = []
    ignorados: list[tuple[int, str]] = []

    for idx, row in df.iterrows():
        linha = idx + 1  # type: ignore[operator]

        # col 0 deve ser número inteiro do pedido
        try:
            num = int(str(row[0]).strip().split(".")[0])
        except (ValueError, TypeError):
            continue  # cabeçalhos e linhas de separação

        def col(i: int, default: str = "") -> str:
            val = str(row[i]).strip() if i < len(row) else default
            # remove "nan" do pandas
            return val if val.lower() not in ("nan", "") else default

        # col(1) pode ser datetime object direto do pandas — não converter para str
        date_raw    = row[1] if 1 < len(row) else None
        customer_nm = col(5)
        item_desc   = col(6)
        value_str   = col(9)
        obs         = col(10)
        conhece     = col(12)

        date_obj = parse_date(date_raw)
        value    = parse_value(value_str)

        if not customer_nm:
            ignorados.append((linha, f"pedido #{num}: cliente vazio"))
            continue

        pedidos.append({
            "linha":       linha,
            "number":      num,
            "date":        date_obj,
            "customer_nm": customer_nm,
            "item_desc":   item_desc,
            "value":       value,
            "obs":         obs,
            "conhece":     conhece,
        })

    print(f"[CSV] {len(pedidos)} pedidos lidos  |  {len(ignorados)} linhas ignoradas")

    if args.dry_run:
        print("\n── DRY-RUN: nenhum dado será gravado ──")
        for p in pedidos[:15]:
            prods = extrair_produtos(p["item_desc"])
            print(
                f"  #{p['number']:>4}  {p['customer_nm']:<28}  "
                f"R${p['value']:>8.2f}  {prods}"
            )
        if len(pedidos) > 15:
            print(f"  ... e mais {len(pedidos) - 15} pedidos")
        return

    # ── 2. Abre o banco ───────────────────────────────────────────────────────
    db = SessionLocal()
    logs: list[str] = []

    def log(msg: str):
        print(msg)
        logs.append(msg)

    try:
        # ── 2a. Opcional: reset ───────────────────────────────────────────────
        if args.reset:
            log("[RESET] Apagando todos os pedidos existentes...")
            db.execute(text("DELETE FROM order_items"))
            db.execute(text("DELETE FROM order_status_history"))
            db.execute(text("DELETE FROM orders"))
            db.commit()
            log("[RESET] Concluído.")

        # ── 2b. Carrega maps do banco ─────────────────────────────────────────
        log("[DB] Carregando clientes...")
        cust_rows = db.execute(
            text("SELECT id, name FROM customers")
        ).fetchall()
        customers_map: dict[str, int] = {normalizar(r[1]): r[0] for r in cust_rows}
        customers_nome: dict[str, str] = {normalizar(r[1]): r[1] for r in cust_rows}
        log(f"[DB] {len(customers_map)} clientes carregados")

        log("[DB] Carregando produtos...")
        prod_rows = db.execute(
            text("SELECT id, name FROM products")
        ).fetchall()
        products_map: dict[str, int] = {normalizar(r[1]): r[0] for r in prod_rows}
        products_nome: dict[str, str] = {normalizar(r[1]): r[1] for r in prod_rows}
        log(f"[DB] {len(products_map)} produtos carregados")

        # ── 2c. Pedidos já existentes ─────────────────────────────────────────
        existing = {
            r[0] for r in db.execute(text("SELECT number FROM orders")).fetchall()
        }
        log(f"[DB] {len(existing)} pedidos já existem no banco")

        # ── 3. Acumuladores ───────────────────────────────────────────────────
        customer_conhece: dict[int, set[str]] = {}
        product_obs: dict[int, set[str]] = {}
        nao_mapeados_clientes: list[str] = []
        nao_mapeados_produtos: list[tuple[int, str]] = []

        inseridos   = 0
        pulados     = 0
        com_erro    = 0

        # ── 4. Pré-carrega pedidos que já têm itens ───────────────────────────
        existing_with_items = {
            r[0] for r in db.execute(text(
                "SELECT DISTINCT o.number FROM orders o "
                "JOIN order_items oi ON oi.order_id = o.id"
            )).fetchall()
        }
        log(f"[DB] {len(existing_with_items)} pedidos já têm itens")
        itens_adicionados = 0
        datas_corrigidas  = 0

        # ── 4. Loop de pedidos ────────────────────────────────────────────────
        for p in pedidos:
            num = p["number"]

            # Pedido já existe E já tem itens → só corrige a data se necessário
            if num in existing_with_items:
                if p["date"]:
                    date_val = p["date"].strftime("%Y-%m-%d 12:00:00+00")
                    # Verifica se a data no banco é o fallback errado (2014-01-01)
                    # ou se difere da data correta do XLSX
                    atual_dt = db.execute(
                        text("SELECT created_at FROM orders WHERE number = :n"),
                        {"n": num}
                    ).scalar()
                    atual_str = str(atual_dt)[:10] if atual_dt else ""
                    correta_str = p["date"].strftime("%Y-%m-%d")
                    if atual_str != correta_str:
                        db.execute(
                            text("UPDATE orders SET created_at = :dt, updated_at = :dt WHERE number = :n"),
                            {"dt": date_val, "n": num}
                        )
                        datas_corrigidas += 1
                pulados += 1
                continue

            # ── 4a. Resolve cliente ───────────────────────────────────────────
            chave_cli = normalizar(p["customer_nm"])

            # tenta mapa manual primeiro
            cust_id: int | None = None
            if chave_cli in MAP_CLIENTES:
                nome_alvo = normalizar(MAP_CLIENTES[chave_cli])
                cust_id = customers_map.get(nome_alvo)
                if cust_id:
                    log(f"[MAP] Pedido #{num}: cliente '{p['customer_nm']}' → '{MAP_CLIENTES[chave_cli]}'")

            if cust_id is None:
                cust_id, cust_chave_banco, cust_score = fuzzy_find(
                    p["customer_nm"], customers_map, limiar
                )
                if cust_id:
                    if cust_score == 100:
                        log(f"[OK]    Pedido #{num}: cliente exato '{p['customer_nm']}'")
                    else:
                        log(
                            f"[FUZZY] Pedido #{num}: cliente '{p['customer_nm']}' "
                            f"→ '{customers_nome.get(cust_chave_banco or '', '?')}' "
                            f"(score={cust_score})"
                        )

            if cust_id is None:
                msg = f"Pedido #{num}: cliente não encontrado: '{p['customer_nm']}'"
                log(f"[ERRO]  {msg}")
                nao_mapeados_clientes.append(p["customer_nm"])
                com_erro += 1
                continue

            # ── 4b. Insere order ou recupera id do existente ──────────────────
            try:
                db.execute(text("SAVEPOINT sp_pedido"))

                date_val = (
                    p["date"].strftime("%Y-%m-%d 12:00:00+00")
                    if p["date"]
                    else "2014-01-01 12:00:00+00"
                )

                # Tenta inserir; se já existe (sem itens), busca o id
                order_id: int | None = db.execute(text("""
                    INSERT INTO orders
                        (number, customer_id, status, total, created_at, updated_at)
                    VALUES
                        (:num, :cid, 'PAID', :total, :dt, :dt)
                    ON CONFLICT (number) DO NOTHING
                    RETURNING id
                """), {
                    "num":   num,
                    "cid":   cust_id,
                    "total": p["value"],
                    "dt":    date_val,
                }).scalar()

                if order_id is None:
                    # Pedido já existe mas sem itens → busca o id existente
                    order_id = db.execute(
                        text("SELECT id FROM orders WHERE number = :num"),
                        {"num": num}
                    ).scalar()
                    if order_id is None:
                        db.execute(text("RELEASE SAVEPOINT sp_pedido"))
                        pulados += 1
                        continue
                    log(f"[PATCH] Pedido #{num}: já existe sem itens, adicionando itens...")
                else:
                    # Pedido novo: insere histórico de status
                    db.execute(text("""
                        INSERT INTO order_status_history (order_id, status, changed_at)
                        VALUES (:oid, 'PAID', :dt)
                    """), {"oid": order_id, "dt": date_val})

                # ── 4c. Itens do pedido ───────────────────────────────────────
                entradas = extrair_produtos(p["item_desc"])
                total_qty = sum(q for q, _ in entradas) or 1
                unit_price = round(p["value"] / total_qty, 2) if p["value"] > 0 else 0.0

                for qty, pname in entradas:
                    chave_prod = normalizar(pname)
                    prod_id: int | None = None

                    # mapa manual
                    if chave_prod in MAP_PRODUTOS:
                        nome_alvo_p = normalizar(MAP_PRODUTOS[chave_prod])
                        prod_id = products_map.get(nome_alvo_p)
                        if prod_id:
                            log(f"[MAP] Pedido #{num}: produto '{pname}' → '{MAP_PRODUTOS[chave_prod]}'")

                    if prod_id is None:
                        prod_id, prod_chave_banco, prod_score = fuzzy_find(
                            pname, products_map, limiar
                        )
                        if prod_id:
                            if prod_score == 100:
                                log(f"[OK]    Pedido #{num}: produto exato '{pname}'")
                            else:
                                log(
                                    f"[FUZZY] Pedido #{num}: produto '{pname}' "
                                    f"→ '{products_nome.get(prod_chave_banco or '', '?')}' "
                                    f"(score={prod_score})"
                                )

                    if prod_id is None:
                        log(f"[WARN]  Pedido #{num}: produto não encontrado: '{pname}'")
                        nao_mapeados_produtos.append((num, pname))
                        continue

                    db.execute(text("""
                        INSERT INTO order_items
                            (order_id, product_id, quantity, unit_price)
                        VALUES
                            (:oid, :pid, :qty, :price)
                        ON CONFLICT (order_id, product_id) DO NOTHING
                    """), {"oid": order_id, "pid": prod_id, "qty": qty, "price": unit_price})
                    itens_adicionados += 1

                    if p["obs"]:
                        product_obs.setdefault(prod_id, set()).add(p["obs"].strip())

                # "da onde eu conhece"
                if p["conhece"]:
                    customer_conhece.setdefault(cust_id, set()).add(p["conhece"].strip())

                db.execute(text("RELEASE SAVEPOINT sp_pedido"))
                inseridos += 1

            except Exception as exc:
                db.execute(text("ROLLBACK TO SAVEPOINT sp_pedido"))
                db.execute(text("RELEASE SAVEPOINT sp_pedido"))
                msg = f"Pedido #{num}: erro ao inserir → {exc}"
                log(f"[ERRO]  {msg}")
                com_erro += 1

        # ── 5. Commit dos pedidos ─────────────────────────────────────────────
        db.commit()
        log(f"\n[ORDERS] Inseridos: {inseridos}  |  Datas corrigidas: {datas_corrigidas}  |  Itens adicionados: {itens_adicionados}  |  Pulados: {pulados}  |  Erros: {com_erro}")

        # ── 6. Atualiza customers.notes ───────────────────────────────────────
        log("\n[DB] Atualizando notes dos clientes...")
        upd_cli = 0
        for cid, conhece_set in customer_conhece.items():
            nova_info = ", ".join(sorted(conhece_set))
            atual = db.execute(
                text("SELECT notes FROM customers WHERE id = :id"), {"id": cid}
            ).scalar() or ""
            if nova_info not in atual:
                novo = (atual + "\n" + nova_info).strip() if atual else nova_info
                db.execute(
                    text("UPDATE customers SET notes = :n WHERE id = :id"),
                    {"n": novo[:1000], "id": cid},
                )
                upd_cli += 1
        db.commit()
        log(f"[DB] {upd_cli} clientes com notes atualizados")

        # ── 7. Atualiza products.description ─────────────────────────────────
        log("[DB] Atualizando description dos produtos...")
        upd_prod = 0
        for pid, obs_set in product_obs.items():
            nova_info = ", ".join(sorted(obs_set))
            atual = db.execute(
                text("SELECT description FROM products WHERE id = :id"), {"id": pid}
            ).scalar() or ""
            if nova_info not in atual:
                novo = (atual + "\n" + nova_info).strip() if atual else nova_info
                db.execute(
                    text("UPDATE products SET description = :d WHERE id = :id"),
                    {"d": novo, "id": pid},
                )
                upd_prod += 1
        db.commit()
        log(f"[DB] {upd_prod} produtos com description atualizados")

        # ── 8. Relatório final ────────────────────────────────────────────────
        log("\n╔══════════════════════════════════════════════╗")
        log("║          RESUMO DA IMPORTACAO                ║")
        log("╠══════════════════════════════════════════════╣")
        log(f"║  Pedidos processados:        {len(pedidos):>6}           ║")
        log(f"║  Pedidos novos inseridos:    {inseridos:>6}           ║")
        log(f"║  Datas corrigidas:           {datas_corrigidas:>6}           ║")
        log(f"║  Itens adicionados (patch):  {itens_adicionados:>6}           ║")
        log(f"║  Pedidos completos (pulados):{pulados:>6}           ║")
        log(f"║  Pedidos com erro:           {com_erro:>6}           ║")
        log(f"║  Clientes atualizados:       {upd_cli:>6}           ║")
        log(f"║  Produtos atualizados:       {upd_prod:>6}           ║")
        log("╚══════════════════════════════════════════════╝")

        if nao_mapeados_clientes:
            log(f"\n[AVISO] {len(set(nao_mapeados_clientes))} clientes NÃO encontrados no banco:")
            for c in sorted(set(nao_mapeados_clientes)):
                log(f"  ✗ '{c}'")
            log("  → Adicione-os ao MAP_CLIENTES ou cadastre-os antes de reimportar.")

        if nao_mapeados_produtos:
            log(f"\n[AVISO] {len(nao_mapeados_produtos)} ocorrência(s) de produto NÃO mapeado:")
            vistos: set[str] = set()
            for onum, pname in nao_mapeados_produtos:
                if pname not in vistos:
                    log(f"  ✗ '{pname}'  (ex: pedido #{onum})")
                    vistos.add(pname)
            log("  → Adicione-os ao MAP_PRODUTOS ou cadastre-os antes de reimportar.")

    except Exception as e:
        db.rollback()
        log(f"\n[ERRO FATAL] {e}")
        raise
    finally:
        db.close()

        # Salva log em arquivo
        with open(LOG_PATH, "w", encoding="utf-8") as flog:
            flog.write("\n".join(logs))
        print(f"\n[LOG] Detalhes salvos em: {LOG_PATH}")


if __name__ == "__main__":
    main()
