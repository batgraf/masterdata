#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import io
import json
from pathlib import Path
from typing import List, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from db import get_connection, update_product, insert_change_log


# JSON z polami: id (ID_produktu), nazwa, sku, ean, producent – dopasowanie 1:1 po ID_produktu
RAW_JSON = [
    {"id": 6757, "nazwa": "Grzejnik łazienkowy SOLEN 2 biały 530x1000mm 375W", "sku": "SolenB0822", "ean": "5907718041811", "producent": "Imers"},
    {"id": 6758, "nazwa": "Grzejnik łazienkowy SOLEN 3 biały 530x1200mm 455W", "sku": "SolenB0832", "ean": "5907718041828", "producent": "Imers"},
    {"id": 6759, "nazwa": "Grzejnik łazienkowy SOLEN 1 czarny 530x800mm 302W", "sku": "SolenCZ0812", "ean": "5907718041835", "producent": "Imers"},
    {"id": 6760, "nazwa": "Grzejnik łazienkowy SOLEN 2 czarny 530x1000mm 375W", "sku": "SolenCZ0822", "ean": "5907718041842", "producent": "Imers"},
    {"id": 6762, "nazwa": "Grzejnik łazienkowy SOLEN 1 chrom 530x800mm 302W", "sku": "SolenCH0810", "ean": "5907718041866", "producent": "Imers"},
    {"id": 6763, "nazwa": "Grzejnik łazienkowy SOLEN 2 chrom 530x1000mm 375W", "sku": "SolenCH0820", "ean": "5907718041873", "producent": "Imers"},
    {"id": 6764, "nazwa": "Grzejnik łazienkowy SOLEN 3 chrom 530x1200mm 455W", "sku": "SolenCH0830", "ean": "5907718041880", "producent": "Imers"},
    {"id": 6768, "nazwa": "Panele Podłogowe Dalia Fiori AQUA ZERO 72h Swiss Krono D 4589 AC6 10 mm", "sku": "AUFI4589", "ean": "5901844458901", "producent": "Swiss Krono"},
    {"id": 6770, "nazwa": "Panele Podłogowe Iris Fiori AQUA ZERO 72h Swiss Krono D 4590 AC6 10 mm", "sku": "AUFI4590", "ean": "5901844459007", "producent": "Swiss Krono"},
    {"id": 6773, "nazwa": "Grzejnik łazienkowy SYNTIA 2 biały 530x969mm 251W", "sku": "SyntiaB3022", "ean": "5907718042719", "producent": "Imers"},
    {"id": 6774, "nazwa": "Grzejnik łazienkowy SYNTIA 1 chrom 530x738mm 228W", "sku": "SyntiaCH3010", "ean": "5907718042726", "producent": "Imers"},
    {"id": 6775, "nazwa": "Grzejnik łazienkowy SYNTIA 2 chrom 530x969mm 251W", "sku": "SyntiaCH3020", "ean": "5907718042733", "producent": "Imers"},
    {"id": 6777, "nazwa": "Grzejnik łazienkowy SYNTIA 2 mosiądz 530x969mm 251W", "sku": "SyntiaM3021", "ean": "5907718042757", "producent": "Imers"},
    {"id": 6778, "nazwa": "Grzejnik łazienkowy SYNTIA 1 czarny 530x738mm 228W", "sku": "SyntiaCZ3012", "ean": "5907718042764", "producent": "Imers"},
    {"id": 6783, "nazwa": "Panele Podłogowe Dąb Moon Infinity Swiss Krono D 3728 AC5 10 mm", "sku": "15IQ3728", "ean": "5901844372801", "producent": "Swiss Krono"},
    {"id": 6785, "nazwa": "Panele Podłogowe Dąb Moon Sun Swiss Krono D 4593 AC5 10 mm", "sku": "15IQ4593", "ean": "5901844459304", "producent": "Swiss Krono"},
    {"id": 6787, "nazwa": "Panele Podłogowe Dąb Horizon Infinity Swiss Krono D 4591 AC5 10 mm", "sku": "15IQ4591", "ean": "5901844459106", "producent": "Swiss Krono"},
    {"id": 6792, "nazwa": "Grzejnik łazienkowy TIOMAN 2 biały 530x1200mm 298W", "sku": "TiomanB2622", "ean": "5907718043310", "producent": "Imers"},
    {"id": 6793, "nazwa": "Grzejnik łazienkowy TIOMAN 1 chrom 430x1200mm 265W", "sku": "TiomanCH2610", "ean": "5907718043341", "producent": "Imers"},
    {"id": 6795, "nazwa": "Grzejnik łazienkowy TIOMAN 1 czarny 430x1200mm 265W", "sku": "TiomanCZ2612", "ean": "5907718043365", "producent": "Imers"},
    {"id": 6798, "nazwa": "Panele podłogowe Dąb Eagle Volo AQUA ZERO 72h Swiss Krono D 4574 AC5 8 mm", "sku": "D 4574", "ean": "5901844457409", "producent": "Swiss Krono"},
    {"id": 6802, "nazwa": "Panele podłogowe Dąb Condor Volo AQUA ZERO 72h Swiss Krono D 40254 AC5 8 mm", "sku": "D 40254", "ean": "5901844402546", "producent": "Swiss Krono"},
    {"id": 6803, "nazwa": "Panele podłogowe Dąb Stork Volo AQUA ZERO 72h Swiss Krono D 4573 AC5 8 mm", "sku": "D 4573", "ean": "5901844457300", "producent": "Swiss Krono"},
    {"id": 6804, "nazwa": "Panele podłogowe Dąb Hawk Volo AQUA ZERO 72h Swiss Krono D 4577 AC5 8 mm", "sku": "D 4577", "ean": "5901844457706", "producent": "Swiss Krono"},
    {"id": 6805, "nazwa": "Panele podłogowe Dąb Cortado Sefora Swiss Krono 40444 AC5 10 mm", "sku": "AUSF40444", "ean": "5901844404441", "producent": "Swiss Krono"},
    {"id": 6806, "nazwa": "Panele podłogowe Dąb Cappucino Sefora Swiss Krono 40454 AC5 10 mm", "sku": "AUSF40454", "ean": "5901844404540", "producent": "Swiss Krono"},
    {"id": 6808, "nazwa": "Panele podłogowe Dąb Macchiato Sefora Swiss Krono 40464 AC5 10 mm", "sku": "AUSF40464", "ean": "5901844404649", "producent": "Swiss Krono"},
    {"id": 6809, "nazwa": "Panele podłogowe Dąb Americano Sefora Swiss Krono 40474 AC5 10 mm", "sku": "AUSF40474", "ean": "5901844404748", "producent": "Swiss Krono"},
    {"id": 6810, "nazwa": "Panele podłogowe Dąb Breve Sefora Swiss Krono 40484 AC5 10 mm", "sku": "AUSF40484", "ean": "5901844404847", "producent": "Swiss Krono"},
    {"id": 6811, "nazwa": "Panele podłogowe Dąb Ristretto Sefora Swiss Krono 40494 AC5 10 mm", "sku": "AUSF40494", "ean": "5901844404946", "producent": "Swiss Krono"},
    {"id": 6812, "nazwa": "Panele podłogowe Dąb Espresso Sefora Swiss Krono 40504 AC5 10 mm", "sku": "AUSF40504", "ean": "5901844405042", "producent": "Swiss Krono"},
    {"id": 6886, "nazwa": "Grzejnik elektryczny Instal Projekt Giulietta Elec BIOE1-50/120C1", "sku": "BIOE1-50/120C1", "ean": "5901614349127", "producent": "Instal Projekt"},
    {"id": 8284, "nazwa": "Panele podłogowe Dąb Forte Symfonia AQUA ZERO 72h Swiss Krono D 40074 AC5 12 mm", "sku": "AUSY40074", "ean": "5901844400740", "producent": "Swiss Krono"},
    {"id": 8285, "nazwa": "Panele podłogowe Dąb Adagio Symfonia AQUA ZERO 72h Swiss Krono D 40414 AC5 12 mm", "sku": "AUSY40414", "ean": "5901844404144", "producent": "Swiss Krono"},
    {"id": 9384, "nazwa": "Lampa wisząca PASTELO 5 czarna 5x12W G9 Sollux Lighting", "sku": "SL.0459", "ean": "5902622426809", "producent": "Sollux"},
    {"id": 9385, "nazwa": "Lampa wisząca PASTELO 5 biała 5x12W G9 Sollux Lighting", "sku": "SL.0453", "ean": "5902622426748", "producent": "Sollux"},
    {"id": 9386, "nazwa": "Lampa wisząca PASTELO 5 złota 5x12W G9 Sollux Lighting", "sku": "SL.0466", "ean": "5902622426878", "producent": "Sollux"},
    {"id": 9387, "nazwa": "Lampa wisząca PASTELO 5P złota 5x8W G9 Sollux Lighting", "sku": "SL.0472", "ean": "5902622426939", "producent": "Sollux"},
    {"id": 9388, "nazwa": "Lampa wisząca PASTELO 5P biała 5x8W G9 Sollux Lighting", "sku": "SL.0474", "ean": "5902622426953", "producent": "Sollux"},
    {"id": 9389, "nazwa": "Lampa wisząca PASTELO 5P czarna 5x8W G9 Sollux Lighting", "sku": "SL.0475", "ean": "5902622426960", "producent": "Sollux"},
    {"id": 10460, "nazwa": "Szafka Górna Comad RETRO 40cm 1 Drzwi", "sku": "RETRO 40cm", "ean": "5905167761007", "producent": "Comad"},
    {"id": 11147, "nazwa": "Lampa wisząca PASTELO 1 złoty połysk 1x8W G9 Sollux Lighting", "sku": "SL.0461", "ean": "5902622426823", "producent": "Sollux"},
    {"id": 11150, "nazwa": "Lampa wisząca PASTELO 5L beton 5x8W G9 Sollux Lighting", "sku": "SL.0475", "ean": "5902622426960", "producent": "Sollux"},
    {"id": 15555, "nazwa": "Zapasowy klosz Dorado 6 plafon LP-002/6C", "sku": "LP-002/6C", "ean": "5902365124114", "producent": "Light Prestige"},
    {"id": 15556, "nazwa": "Zapasowy klosz Alisa LP-005/6P WH", "sku": "LP-005/6P WH", "ean": "5902365121021", "producent": "Light Prestige"},
    {"id": 15557, "nazwa": "Zapasowy klosz Alisa LP-005/6P transp", "sku": "LP-005/6P TR", "ean": "5902365123100", "producent": "Light Prestige"},
    {"id": 16900, "nazwa": "BELLANTI Zestaw Empoli 3 osobowy + stolik | Beż", "sku": "ZS3BELL_EMP_B", "ean": "5907367280258", "producent": "Bellanti"},
    {"id": 17366, "nazwa": "BELLANTI Zestaw Empoli 2 osobowy + stolik | Beż", "sku": "ZS2BELL_EMP_B", "ean": "5907367280296", "producent": "Bellanti"},
    {"id": 17368, "nazwa": "BELLANTI Zestaw Empoli 4 osobowy + stolik | Beż", "sku": "ZS4BELL_EMP_B", "ean": "5907367280463", "producent": "Bellanti"},
    {"id": 17369, "nazwa": "BELLANTI Zestaw Empoli 7 osobowy + stolik | Beż", "sku": "ZS7BELL_EMP_B", "ean": "5907367280487", "producent": "Bellanti"},
    {"id": 17370, "nazwa": "BELLANTI Zestaw Pienza 5 osobowy + stolik | Beż", "sku": "ZS5BELL_PIE_B", "ean": "5907367280432", "producent": "Bellanti"},
    {"id": 17375, "nazwa": "BELLANTI Zestaw Pienza 7 osobowy + stolik | Beż", "sku": "ZS7BELL_PIE_B", "ean": "5907367280548", "producent": "Bellanti"},
    {"id": 17376, "nazwa": "BELLANTI Zestaw Pienza 3 osobowy + stolik | Beż", "sku": "ZS3BELL_PIE_B", "ean": "5907367280401", "producent": "Bellanti"},
    {"id": 17382, "nazwa": "BELLANTI Zestaw Pienza 2 osobowy + stolik | Beż", "sku": "ZS2BELL_PIE_B", "ean": "5907367280340", "producent": "Bellanti"},
    {"id": 17388, "nazwa": "BELLANTI Zestaw Livorno 4 osobowy + stolik | Szary | Czarny", "sku": "ZS4BELL_LIV_LG", "ean": "5907367280531", "producent": "Bellanti"},
    {"id": 17389, "nazwa": "BELLANTI Zestaw Livorno 2 osobowy + stolik | Szary | Czarny", "sku": "ZS2BELL_LIV_LG", "ean": "5907367280333", "producent": "Bellanti"},
    {"id": 17390, "nazwa": "BELLANTI Zestaw Livorno 3 osobowy + stolik | Szary | Czarny", "sku": "ZS3BELL_LIV_LG", "ean": "5907367280272", "producent": "Bellanti"},
    {"id": 17391, "nazwa": "BELLANTI Zestaw Firenze 4 osobowy + stolik | Antracyt", "sku": "ZS4BELL_FIR_DG", "ean": "5907367280524", "producent": "Bellanti"},
    {"id": 17392, "nazwa": "BELLANTI Zestaw Firenze 3 osobowy + stolik | Antracyt", "sku": "ZS3BELL_FIR_DG", "ean": "5907367280425", "producent": "Bellanti"},
    {"id": 17393, "nazwa": "BELLANTI Zestaw Firenze 2 osobowy + stolik | Antracyt", "sku": "ZS2BELL_FIR_DG", "ean": "5907367280326", "producent": "Bellanti"},
    {"id": 17394, "nazwa": "BELLANTI Zestaw Carrara 5 osobowy + 2 x stolik | Beż", "sku": "ZS5BELL_CAR_B", "ean": "5907367280500", "producent": "Bellanti"},
    {"id": 17395, "nazwa": "BELLANTI Zestaw Carrara 4 osobowy + 2 x stolik | Beż", "sku": "ZS4BELL_CAR_B", "ean": "5907367280319", "producent": "Bellanti"},
    {"id": 17406, "nazwa": "BELLANTI Zestaw Carrara 2 osobowy + 2 x stolik | Beż", "sku": "ZS2BELL_CAR_B", "ean": "5907367280290", "producent": "Bellanti"},
    {"id": 17407, "nazwa": "BELLANTI Zestaw Siena 7 osobowy + stolik | Antracyt", "sku": "ZS7BELL_SIE_DG", "ean": "5907367280494", "producent": "Bellanti"},
    {"id": 17408, "nazwa": "BELLANTI Zestaw Siena 5 osobowy + stolik | Antracyt", "sku": "ZS5BELL_SIE_DG", "ean": "5907367280302", "producent": "Bellanti"},
    {"id": 17410, "nazwa": "BELLANTI Zestaw Siena 3 osobowy + stolik | Antracyt", "sku": "ZS3BELL_SIE_DG", "ean": "5907367280265", "producent": "Bellanti"},
    {"id": 17412, "nazwa": "BELLANTI Zestaw Siena 2 osobowy + stolik | Antracyt", "sku": "ZS2BELL_SIE_DG", "ean": "5907367280234", "producent": "Bellanti"},
    {"id": 17413, "nazwa": "BELLANTI Zestaw Bucine 4 osobowy + stolik | Beż | Teak", "sku": "ZS4BELL_BUC_B", "ean": "5907367280463", "producent": "Bellanti"},
    {"id": 17414, "nazwa": "BELLANTI Zestaw Bucine 3 osobowy + stolik | Beż | Teak", "sku": "ZS3BELL_BUC_B", "ean": "5907367280449", "producent": "Bellanti"},
    {"id": 17416, "nazwa": "BELLANTI Zestaw Bucine 2 osobowy + stolik | Beż | Teak", "sku": "ZS2BELL_BUC_B", "ean": "5907367280289", "producent": "Bellanti"},
    {"id": 17468, "nazwa": "BELLANTI Zestaw Bucine 4 osobowy + stolik | Czarny | Teak", "sku": "ZS4BELL_BUC_A", "ean": "5907367280470", "producent": "Bellanti"},
    {"id": 17474, "nazwa": "BELLANTI Zestaw Bucine 3 osobowy + stolik | Czarny | Teak", "sku": "ZS3BELL_BUC_A", "ean": "5907367280456", "producent": "Bellanti"},
    {"id": 17475, "nazwa": "BELLANTI Zestaw Bucine 2 osobowy + stolik | Czarny | Teak", "sku": "ZS2BELL_BUC_A", "ean": "5907367280285", "producent": "Bellanti"},
    {"id": 17476, "nazwa": "BELLANTI Zestaw Arezzo 4 osobowy + stolik | Szary | Czarny", "sku": "ZS4BELL_ARE_LG", "ean": "5907367280357", "producent": "Bellanti"},
    {"id": 17478, "nazwa": "BELLANTI Zestaw Arezzo 2 osobowy + stolik | Szary | Czarny", "sku": "ZS2BELL_ARE_LG", "ean": "5907367280350", "producent": "Bellanti"},
    {"id": 17489, "nazwa": "BELLANTI Zestaw Prato 7 osobowy + stolik | Szary | Teak", "sku": "ZS7BELL_PRA_G", "ean": "5907367280555", "producent": "Bellanti"},
    {"id": 17490, "nazwa": "BELLANTI Zestaw Certaldo 4 osobowy + stolik | Antracyt", "sku": "ZS4BELL_CER_DG", "ean": "5907367280364", "producent": "Bellanti"},
    {"id": 17491, "nazwa": "BELLANTI Zestaw Prato 3 osobowy + stolik | Szary | Teak", "sku": "ZS3BELL_PRA_G", "ean": "5907367280371", "producent": "Bellanti"},
    {"id": 17492, "nazwa": "BELLANTI Zestaw Prato 2 osobowy + stolik | Szary | Teak", "sku": "ZS2BELL_PRA_G", "ean": "5907367280370", "producent": "Bellanti"},
    {"id": 17493, "nazwa": "BELLANTI Zestaw Carrara 5 osobowy + 2 x stolik | Ciemny Beż", "sku": "ZS5BELL_CAR_DB", "ean": "5907367280517", "producent": "Bellanti"},
    {"id": 17496, "nazwa": "BELLANTI Zestaw Certaldo 2 osobowy + stolik | Antracyt", "sku": "ZS2BELL_CER_DG", "ean": "5907367280360", "producent": "Bellanti"},
    {"id": 100142, "nazwa": "HARMONY PASADENA WHITE 7,5 X 30 G1", "sku": "PASADENA WHITE", "ean": "8429991196155", "producent": "Peronda"},
    {"id": 100157, "nazwa": "TUNEL OGRODOWY AW6 6X3X2,1 M FOLIA 4UV", "sku": "TW0017", "ean": "5901322101017", "producent": "Lemar"},
    {"id": 100162, "nazwa": "PŁYTKI PERONDA SAVANNAH SILVER 45,2X45,2 G1", "sku": "SAVANNAH SILVER", "ean": "8429991201507", "producent": "Peronda"},
    {"id": 100165, "nazwa": "TUNEL OGRODOWY C3 3X1,2X0,6 M MINI", "sku": "T00068", "ean": "5901322100683", "producent": "Lemar"},
    {"id": 100166, "nazwa": "PERONDA DUOMO HENLEY-R 45X45 (1,22M) G1", "sku": "HENLEY-R", "ean": "8429991194212", "producent": "Peronda"},
    {"id": 100168, "nazwa": "TUNEL B5 5X2,2X1,9 M 4UV", "sku": "T00074", "ean": "5901322100058", "producent": "Lemar"},
    {"id": 100209, "nazwa": "TUNEL OGRODOWY C6 6X1,2X0,6 M MINI", "sku": "T00076", "ean": "5901322100768", "producent": "Lemar"},
    {"id": 100283, "nazwa": "TUNEL OGRODOWY BV3 3X2,2X1,9M FOLIA 4UV", "sku": "T00V22", "ean": "5901322100324", "producent": "Lemar"},
    {"id": 100307, "nazwa": "PŁYTKA PERONDA DUOMO SAVANNAH BLUE 45,2X45,2 G1", "sku": "PERONDA BLUE", "ean": "8429991201514", "producent": "Peronda"},
    {"id": 100310, "nazwa": "TUNEL OGRODOWY B3 3X2,2X1,9M FOLIA 4UV", "sku": "T00022", "ean": "5901322100034", "producent": "Lemar"},
    {"id": 100312, "nazwa": "PŁYTKA FS ARTISAN OLDKER 33X33 PERONDA", "sku": "FS ARTISAN", "ean": "8429991203303", "producent": "Peronda"},
    {"id": 100352, "nazwa": "PERONDA HOUSE OF VANITY C.HV-34 11X33 G1", "sku": "PERONDA VANITY", "ean": "8429991203525", "producent": "Peronda"},
    {"id": 100353, "nazwa": "PERONDA DUOMO SAVANNACH SAGE 45,2X45,2", "sku": "PERONDA SAGE", "ean": "8429991201521", "producent": "Peronda"},
    {"id": 100368, "nazwa": "PERONDA FS OLDKER 33X33 G1", "sku": "PERONDA OLDKER", "ean": "8429991203303", "producent": "Peronda"},
    {"id": 100382, "nazwa": "GRILL ELEKTRYCZNY MIR-E003", "sku": "MIR-E003", "ean": "5905167732502", "producent": "Mirador"},
    {"id": 100383, "nazwa": "FOTEL HAMAKOWY BRASIL CLASSIC M", "sku": "BRASIL CLASIC M", "ean": "4030454002135", "producent": "Amazonas"},
    {"id": 17494, "nazwa": "BELLANTI Zestaw Carrara 4 osobowy + 2 x stolik | Ciemny Beż", "sku": "ZS4BELL_CAR_DB", "ean": "5907367280510", "producent": "Bellanti"},
    {"id": 17495, "nazwa": "BELLANTI Zestaw Carrara 2 osobowy + 2 x stolik | Ciemny Beż", "sku": "ZS2BELL_CAR_DB", "ean": "5907367280517", "producent": "Bellanti"},
    {"id": 100290, "nazwa": "ZESTAW MEBLI DUISBURG CS9401 71 00", "sku": "CS9401 71 00", "ean": "4003673105436", "producent": "Duisburg"},
    {"id": 100385, "nazwa": "FOLIA NA POJ. DRZWI TUNELU A,B 0,8X1,6M", "sku": "F00043", "ean": "5901322100409", "producent": "Lemar"},
    {"id": 100463, "nazwa": "HUŚTAWKA BOCIANIE GNIAZDO 95 ZIELONA", "sku": "MIRPOL-BG95Z", "ean": "5905167732557", "producent": "Mirpol"},
    {"id": 100510, "nazwa": "PERONDA DUOMO SAVANNAH OXIDE 45,2X45,2 G1", "sku": "OXIDE", "ean": "8429991201538", "producent": "Peronda"},
    {"id": 100511, "nazwa": "PERONDA FS IVY SAGE 45X45 G1", "sku": "SAGE", "ean": "8429991244054", "producent": "Peronda"},
    {"id": 100512, "nazwa": "Kinkiet PASTELO 2 złoty", "sku": "SL.1179", "ean": "5902622421170", "producent": "Sollux"},
    {"id": 100515, "nazwa": "PERONDA DUOMO CHECKER 45X45 G1", "sku": "DUOMO CHECKER", "ean": "8429991194205", "producent": "Peronda"},
    {"id": 100519, "nazwa": "PERONDA FS STAR NIGHT 45X45 G1", "sku": "FS STAR NIGHT", "ean": "8429991186101", "producent": "Peronda"},
    {"id": 100520, "nazwa": "MANACOR OCZKO CZARNE 9 CM", "sku": "LP-232/1D-90 CZARNE", "ean": "5902365123209", "producent": "Light Prestige"},
    {"id": 100587, "nazwa": "LAMELE MDF L AKUSTYCZNE NAT OAK 2800X134X18 OP.6", "sku": "SLB-5014", "ean": "5905167762004", "producent": "Stellar"},
    {"id": 100589, "nazwa": "HARMONY TANGER SAND FLOWER 12,3X12,3", "sku": "TANGER SAND FLOWER", "ean": "8429991196209", "producent": "Peronda"},
    {"id": 100639, "nazwa": "Pergola ogrodowa MIRADOR 80 Solid 3 x 4m Antracyt", "sku": "SUU8034", "ean": "5905167736005", "producent": "Mirador"},
    {"id": 100673, "nazwa": "Rozetka ozdobna 1/2 cala czarny Imers", "sku": "1931CZ", "ean": "5907718049053", "producent": "Imers"},
    {"id": 100744, "nazwa": "Grzejnik łazienkowy SYNTIA 1 chrom 530x738mm 228W", "sku": "SYNTIACH3010", "ean": "5907718042726", "producent": "Imers"},
    {"id": 100749, "nazwa": "GRZEJNIK AWENA (530,508, BIAŁY)", "sku": "GAW35082", "ean": "5907718042801", "producent": "Imers"},
    {"id": 100755, "nazwa": "Grzejnik łazienkowy TIOMAN 2 chrom 530x1200mm 298W", "sku": "TIOMANCH2620", "ean": "5907718043358", "producent": "Imers"},
    {"id": 100774, "nazwa": "Szafa garażowa wielofunkcyjna DETROIT XL Utility", "sku": "219966301", "ean": "8013183115488", "producent": "Keter"},
    {"id": 100786, "nazwa": "Grzejnik elektryczny TRICK Electro czarny 50x120 cm", "sku": "TRKE-50/120C75", "ean": "5901614342203", "producent": "Instal Projekt"},
    {"id": 100817, "nazwa": "Grzejnik łazienkowy MINAS 2 chrom 430x1000mm 368W", "sku": "MINASCH0420", "ean": "5907718041637", "producent": "Imers"},
    {"id": 100906, "nazwa": "Panele Podłogowe Tibet AC5 8 mm", "sku": "BELPOL2024.33", "ean": "5901844203334", "producent": "Swiss Krono"},
    {"id": 100915, "nazwa": "GRZAŁKA ELEKTRYCZNA CHROM 300W", "sku": "AG3300W", "ean": "5901614330101", "producent": "Instal Projekt"},
    {"id": 100386, "nazwa": "FOLIA NA BOK TUNELU A", "sku": "FBA046", "ean": "5901322100416", "producent": "Lemar"},
    {"id": 100561, "nazwa": "GRZEJNIK TIOMAN 530X1200 BIAŁY", "sku": "GT332", "ean": "5907718043310", "producent": "Imers"},
    {"id": 100669, "nazwa": "Lamele Dekoracyjne Białe Matowe MDF do malowania", "sku": "DOMALOWANIA", "ean": "5905167768488", "producent": "Stellar"},
    {"id": 100675, "nazwa": "Komplet złączek IMERS czarny (123)", "sku": "0000000123", "ean": "5907718049206", "producent": "Imers"},
    {"id": 100677, "nazwa": "Komplet złączek IMERS czarny (Zestaw)", "sku": "IMERS-CZAR-KOM", "ean": "5907718049213", "producent": "Imers"},
    {"id": 100719, "nazwa": "Grzejnik łazienkowy TIOMAN 2 biały 530x1200mm 298W", "sku": "TIOMANB2622", "ean": "5907718043310", "producent": "Imers"},
    {"id": 100748, "nazwa": "Grzejnik łazienkowy SYNTIA 2 chrom 530x969mm 251W", "sku": "SYNTIACH3020", "ean": "5907718042733", "producent": "Imers"},
    {"id": 100751, "nazwa": "GRZEJNIK ART (530x1000, GALWANIZOWANY)", "sku": "GPGA324", "ean": "5907718044287", "producent": "Imers"},
    {"id": 100752, "nazwa": "GRZEJNIK ARIES (190x1000, CHROMOWANY)", "sku": "GA1923", "ean": "5907718042559", "producent": "Imers"},
    {"id": 100754, "nazwa": "Rozetka ozdobna 1/2 cala chrom Imers", "sku": "1930", "ean": "5907718049008", "producent": "Imers"},
    {"id": 100776, "nazwa": "GRZEJNIK TIOMAN (530x1200, CHROM)", "sku": "GT333", "ean": "5907718043358", "producent": "Imers"},
    {"id": 100777, "nazwa": "ZAWORY TERMOSTATYCZNE OSIOWE KOMPLET (CHROM PRAWY)", "sku": "AZMOP3", "ean": "5907718046205", "producent": "Imers"},
    {"id": 100778, "nazwa": "ROZETA KOMPLET CHROMOWANY", "sku": "ROZETA", "ean": "5907718049107", "producent": "Imers"},
    {"id": 100779, "nazwa": "GRZEJNIK ARIES (240x1500, RAL 9005 MAT)", "sku": "GA2481", "ean": "5907718042498", "producent": "Imers"},
    {"id": 100781, "nazwa": "ROZETA CZARNY MAT KOMPLET", "sku": "ROZETA CZARNA MAT", "ean": "5907718049121", "producent": "Imers"},
    {"id": 100799, "nazwa": "Grzejnik łazienkowy SYNTIA 2 mosiądz 530x969mm 251W", "sku": "SYNTIAM3021", "ean": "5907718042757", "producent": "Imers"},
    {"id": 100818, "nazwa": "Grzejnik łazienkowy MINAS 3 chrom 430x1200mm 400W", "sku": "MINASCH0430", "ean": "5907718041644", "producent": "Imers"},
    {"id": 100839, "nazwa": "Zawory kątowe RETRO mosiądz 1711", "sku": "1711MOSIĄDZ", "ean": "5907718048001", "producent": "Imers"},
    {"id": 100907, "nazwa": "PERONDA DUOMO RUUZINI 45,2X45,2", "sku": "RUUZINI", "ean": "8429991201545", "producent": "Peronda"},
    {"id": 100914, "nazwa": "ZAWORY RETRO CHROM", "sku": "AZR3", "ean": "5907718048018", "producent": "Imers"},
    {"id": 100924, "nazwa": "Panele Podłogowe Rodos AC5 8 mm v-fuga", "sku": "BELPOL2024.1", "ean": "5901844201118", "producent": "Swiss Krono"},
    {"id": 100973, "nazwa": "Grzejnik elektryczny Mondrian Elect MONE-50/140C31", "sku": "MONE-50/140C31", "ean": "5901614349226", "producent": "Instal Projekt"},
    {"id": 100976, "nazwa": "LIGHTSTONE CREMA GRES REKT. PÓŁPOLER", "sku": "LIGHTSTONE CREMA", "ean": "5903263449318", "producent": "Paradyż"},
    {"id": 100977, "nazwa": "NEVE CREATIVE BEIGE ŚCIANA DEKOR REKT.", "sku": "NEVE BEIGE", "ean": "5903263449509", "producent": "Paradyż"},
    {"id": 100984, "nazwa": "HARMONY POITIERS ROSE 7,5X30 G1", "sku": "POITIERS", "ean": "8429991196148", "producent": "Peronda"},
    {"id": 101064, "nazwa": "Panele podłogowe Dąb Verona Swiss Krono 3787 WG", "sku": "SKWG_89LGV4-3787", "ean": "5901844378704", "producent": "Swiss Krono"},
    {"id": 101071, "nazwa": "Tunel foliowy AW4 [12m2] 4x3x2,1m UV4", "sku": "LEMAR2024T.20", "ean": "5901322100201", "producent": "Lemar"},
    {"id": 101144, "nazwa": "Tunel foliowy BV2 [4,4 m2] 2x2,2x1,9m", "sku": "LEMAR2024.5", "ean": "5901322100225", "producent": "Lemar"},
    {"id": 100676, "nazwa": "Komplet złączek IMERS czarny (125)", "sku": "0000000125", "ean": "5907718049220", "producent": "Imers"},
    {"id": 100747, "nazwa": "Podłączenie środkowe IMERS", "sku": "IMERSPS", "ean": "5907718049305", "producent": "Imers"},
    {"id": 100780, "nazwa": "ZAWORY MODERN (CZARNY) + PEX", "sku": "AZM5", "ean": "5907718047103", "producent": "Imers"},
    {"id": 100819, "nazwa": "GRZEJNIK SYNTIA (530x969, GALWANIZOWANY)", "sku": "GSY39694", "ean": "5907718042788", "producent": "Imers"},
    {"id": 100908, "nazwa": "GRZEJNIK ARIES (190x1000, BIAŁY)", "sku": "GA1922", "ean": "5907718042528", "producent": "Imers"},
    {"id": 100912, "nazwa": "GRZEJNIK ART (530x1000, RAL 9005 MAT)", "sku": "GA321", "ean": "5907718044249", "producent": "Imers"},
    {"id": 100974, "nazwa": "Grzejnik elektryczny Mondrian Elect MONE-50/140C31+G(1)", "sku": "MONE-50/140C31+G(1)", "ean": "5901614349233", "producent": "Instal Projekt"},
    {"id": 100978, "nazwa": "MONPELLI MIX CEGIEŁKA STRUKTURA POŁYSK", "sku": "MONPELLI", "ean": "5903263449608", "producent": "Paradyż"},
    {"id": 100979, "nazwa": "NEVE DARK GREEN ŚCIANA STRUKTURA MAT 19,8X19,8", "sku": "NEVE GREEN", "ean": "5903263449615", "producent": "Paradyż"},
    {"id": 100983, "nazwa": "ZAWORY TERMOSTATYCZNE CZARNE", "sku": "AZTO5", "ean": "5907718046304", "producent": "Imers"},
    {"id": 101044, "nazwa": "Grzejnik elektryczny PIKO Electro biały PIKE-50/110C34", "sku": "PIKE-50/110C34", "ean": "5901614341015", "producent": "Instal Projekt"},
    {"id": 101106, "nazwa": "Panele Podłogowe Lycia AC4 8 mm Jasna Jodełka AGT", "sku": "BELPOL2024.5", "ean": "8697419810505", "producent": "AGT"},
    {"id": 101151, "nazwa": "Folia tunelowa, foliak, tunel ogrodowy", "sku": "LEMAR2024F.10", "ean": "5901322100102", "producent": "Lemar"},
    {"id": 101164, "nazwa": "GEAR BOX FOR PERGOLA", "sku": "GEAR BOX", "ean": "5905167736203", "producent": "Mirador"},
    {"id": 101175, "nazwa": "Folia BV2 płachta główna 2x2,2x1,9m", "sku": "LEMAR2024F.16", "ean": "5901322100225", "producent": "Lemar"},
    {"id": 101216, "nazwa": "Panele Podłogowe Parima AC4 8 mm Naturalny Jodełka", "sku": "BELPOL2024.2", "ean": "8697419810512", "producent": "AGT"},
    {"id": 101252, "nazwa": "Płytka ścienno-podłogowa MARQUINA BLACK 90x90 MAT", "sku": "25978", "ean": "8429991259782", "producent": "Peronda"},
    {"id": 101262, "nazwa": "Szafka stojąca KETER KIS MOBY low - grafit", "sku": "219965686", "ean": "8013183112104", "producent": "Keter"},
    {"id": 101322, "nazwa": "Skrzynia ogrodowa KETER Glenwood Storage Box 390 l", "sku": "15738", "ean": "7290106922662", "producent": "Keter"},
    {"id": 101336, "nazwa": "Panele Podłogowe Alesta AC4 8 mm Szara Jodełka AGT", "sku": "BELPOL2024.8", "ean": "8697419810529", "producent": "AGT"},
    {"id": 101338, "nazwa": "Rozetka ozdobna 1/2 cala biały Imers", "sku": "1931B", "ean": "5907718049015", "producent": "Imers"},
    {"id": 101385, "nazwa": "Grzejnik elektryczny GIULIETTA GLTE-60/160C31", "sku": "GLTE-60/160C31", "ean": "5901614349103", "producent": "Instal Projekt"},
    {"id": 101390, "nazwa": "Panele Podłogowe Dąb Fantasy AQUA ZERO Swiss Krono", "sku": "84MQ4584", "ean": "5901844458406", "producent": "Swiss Krono"},
    {"id": 101396, "nazwa": "HAMPTON CONCRETE 824 Szafka pod umywalkę", "sku": "HAMPTON CONCRETE 824", "ean": "5905167761502", "producent": "Comad"},
    {"id": 101399, "nazwa": "CAPRI LAMPA LED ALA 2 BLACK 60 CM", "sku": "CAPRI LED ALA", "ean": "5905167761601", "producent": "Comad"},
    {"id": 100913, "nazwa": "GRZEJNIK SYNTIA 969 CHROMOWANY ZDC GL", "sku": "GSY39693", "ean": "5907718042733", "producent": "Imers"},
    {"id": 100951, "nazwa": "ZAWORY RETRO GALWANIZOWANE", "sku": "AZR4", "ean": "5907718048025", "producent": "Imers"},
    {"id": 100980, "nazwa": "NEVE CREATIVE DARK GREEN ŚCIANA MAT", "sku": "NEVE GREEN MAT", "ean": "5903263449622", "producent": "Paradyż"},
    {"id": 101109, "nazwa": "Grzejnik łazienkowy MINAS 6 mosiądz 530x1200mm 482W", "sku": "MINASM0461", "ean": "5907718041736", "producent": "Imers"},
    {"id": 101226, "nazwa": "Gamrat UNIWERSALNY PROFIL WPC CLASSIC Ciemny Brąz (206)", "sku": "0000000206", "ean": "5907437140901", "producent": "Gamrat"},
    {"id": 101272, "nazwa": "Narożnik zewnętrzny uniwersalny NGF56/SG56 WIŚNIA", "sku": "NG0V06", "ean": "5905167769010", "producent": "Arbiton"},
    {"id": 101273, "nazwa": "Narożnik zewnętrzny uniwersalny NGF56/SG56 D.STARY", "sku": "NG0V19", "ean": "5905167769027", "producent": "Arbiton"},
    {"id": 101387, "nazwa": "FO SZKLARNIA 2X0,8X1,7M FOLIA NA WARZYWA", "sku": "GT0006", "ean": "5901322100607", "producent": "Lemar"},
    {"id": 101395, "nazwa": "HAMPTON CONCRETE 800 SŁUPEK WYSOKI 2D", "sku": "800 KPL SŁ.WYS.2D", "ean": "5905167761519", "producent": "Comad"},
    {"id": 101398, "nazwa": "UMYWALKA NABLATOWA 6275 SLIM CZARNY MAT", "sku": "SLIM 2 E-6275 DP", "ean": "5905167761557", "producent": "Comad"},
    {"id": 101401, "nazwa": "GRZEJNIK ARIES (240x1500, BIAŁY)", "sku": "GA24015002", "ean": "5907718042405", "producent": "Imers"},
    {"id": 101415, "nazwa": "Zestaw 3 x Panel Żaluzjowy boczny aluminiowy 90 x 238", "sku": "OX3", "ean": "5905167735114", "producent": "Nordeck"},
    {"id": 101461, "nazwa": "Płytka ścienno-podłogowa SATYA-B 60X120 R9 krem", "sku": "25432", "ean": "8429991254329", "producent": "Peronda"},
    {"id": 101481, "nazwa": "Panele Podłogowe Dąb Newcastle AC4 8 mm", "sku": "MBP2004", "ean": "5901844200418", "producent": "Swiss Krono"},
    {"id": 101504, "nazwa": "NORDECK Wspornik regulowany 18-32mm", "sku": "FTW-18-32", "ean": "5905167731505", "producent": "Nordeck"},
    {"id": 101510, "nazwa": "Domek narzędziowy metalowy NORDVIC Magni 283x251 cm", "sku": "NORD9X8LG_MAGNI", "ean": "5905167731987", "producent": "Nordvic"},
    {"id": 101523, "nazwa": "MIRADOR 80 Solid 3x2,4m + Roleta 3m", "sku": "ZSMIRADOR3X2,4_R3", "ean": "5905167736012", "producent": "Mirador"},
    {"id": 101526, "nazwa": "Peronda Planet anth/60x60/A/R G1", "sku": "PERONDA PLANET ANTH", "ean": "8429991201552", "producent": "Peronda"},
    {"id": 101528, "nazwa": "Grzejnik łazienkowy GESI 1 mosiądz 1000x530mm 263W", "sku": "GESI2911MO", "ean": "5907718042993", "producent": "Imers"},
    {"id": 101560, "nazwa": "Sztacheta kompozytowa ze strukturą drewna NORDECK", "sku": "NORDECK001", "ean": "5905167732106", "producent": "Nordeck"},
    {"id": 101570, "nazwa": "Grzejnik łazienkowy MINAS 6 czarny 530x1200mm 482W", "sku": "MINASCZ0462", "ean": "5907718041613", "producent": "Imers"},
    {"id": 101577, "nazwa": "Grzejnik łazienkowy TIOMAN 2 czarny 530x1200mm 298W", "sku": "TIOMANCZ2622", "ean": "5907718043372", "producent": "Imers"},
    {"id": 101580, "nazwa": "Zestaw do łączenia Pergoli Nordvic Skyline", "sku": "1PG33244", "ean": "5905167735206", "producent": "Nordvic"},
    {"id": 101125, "nazwa": "Pergola ogrodowa aluminiowa Skyline 3 x 4 m Antracyt", "sku": "NORD4X3_MONTAŻ", "ean": "5905167735008", "producent": "Nordvic"},
    {"id": 101697, "nazwa": "Lamela dachowa Mirador", "sku": "LAM_M01", "ean": "5905167736104", "producent": "Mirador"},
]


def parse_csv(csv_text: str) -> List[Dict[str, Any]]:
    out = []
    r = csv.reader(io.StringIO(csv_text.strip()))
    header = next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        nazwa, id_or_sku, ean, producent = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
        if not nazwa or not ean:
            continue
        id_produktu = None
        try:
            n = int(id_or_sku.strip())
            if n > 0:
                id_produktu = n
        except (ValueError, TypeError):
            pass
        out.append({
            "nazwa": nazwa, "model_kod": id_or_sku,
            "id_produktu": id_produktu, "ean": ean, "producent": producent,
        })
    return out


def _pick_best_row(rows: List[tuple], item: Dict[str, Any], ean: str = "") -> List[tuple]:
    if len(rows) <= 1:
        return rows
    if ean:
        rows = [r for r in rows if (r[3] or "").strip() != ean]
        if len(rows) == 1:
            return rows
        if not rows:
            return []
    nazwa_sz = (item.get("nazwa") or "").strip().lower()
    prod_sz = (item.get("producent") or "").strip().lower()
    matching = [r for r in rows if (r[4] or "").strip().lower() == nazwa_sz]
    if len(matching) == 1:
        return matching
    stop = {"panele", "grzejnik", "dąb", "swiss", "krono", "aurum", "volo", "ac5", "8mm", "10mm", "łazienkowy"}
    tokens = [w for w in nazwa_sz.split() if len(w) > 2 and w not in stop and not w.replace("x", "").replace(".", "").isdigit()]
    scored = []
    for r in rows:
        db_n = (r[4] or "").lower()
        db_p = (r[5] or "").lower()
        score = sum(1 for t in tokens if t in db_n)
        if prod_sz and prod_sz in db_n:
            score += 10
        elif prod_sz and prod_sz in db_p:
            score += 5
        scored.append((score, r))
    best = max(scored, key=lambda x: x[0])
    if best[0] > 0 and sum(1 for s, _ in scored if s == best[0]) == 1:
        return [best[1]]
    return rows


def main() -> None:
    raw = globals().get("RAW_JSON", None)
    data = raw if isinstance(raw, list) and raw and isinstance(raw[0], dict) else parse_csv(globals().get("RAW_CSV", ""))
    has_ean = [x for x in data if x.get("ean")]
    no_ean = [x for x in data if not x.get("ean")]
    print(f"Wczytano: {len(data)} rekordów ({len(has_ean)} z EAN, {len(no_ean)} bez EAN)")
    print()

    updated = 0
    skipped_same = 0
    not_found: List[Dict[str, Any]] = []
    multi: List[Dict[str, Any]] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in data:
                ean = (item.get("ean") or "").strip()
                pk_id = item.get("id")
                sku = (item.get("model_kod") or item.get("sku") or "").strip()
                nazwa = (item.get("nazwa") or "").strip()

                if not ean:
                    not_found.append({**item, "reason": "brak_ean"})
                    continue

                if pk_id is not None and isinstance(pk_id, int) and pk_id > 0:
                    cur.execute('SELECT id, "EAN" FROM products WHERE "ID_produktu" = %s', (float(pk_id),))
                    row = cur.fetchone()
                    if not row and sku:
                        pk_id = None
                    elif not row:
                        not_found.append({**item, "reason": "id_produktu_not_found"})
                        continue
                    elif row:
                        table_id, old_ean = row[0], (row[1] or "").strip() if row[1] else ""
                        if old_ean == ean:
                            skipped_same += 1
                        else:
                            ok = update_product(conn, table_id, "EAN", ean)
                            if ok:
                                try:
                                    insert_change_log(conn, "Arek+Ewa (batch_ean)", pk_id, "EAN", ean)
                                except Exception:
                                    pass
                                updated += 1
                            else:
                                not_found.append({**item, "reason": "update_failed"})
                        continue

                rows = []
                id_prod = item.get("id_produktu")
                if id_prod is not None:
                    cur.execute(
                        'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                        'FROM products WHERE "ID_produktu" = %s',
                        (id_prod,),
                    )
                    rows = cur.fetchall()
                if not rows and sku:
                    cur.execute(
                        'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                        'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                        (sku,),
                    )
                    rows = cur.fetchall()
                    if not rows and sku.startswith("A") and sku[1:].replace("-", "").isalnum():
                        cur.execute(
                            'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                            'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                            (sku[1:],),
                        )
                        rows = cur.fetchall()
                    if not rows and "BELL_" in sku.upper() and "BELLALU" not in sku.upper():
                        alt = sku.replace("BELL_", "BELLALU_")
                        if alt != sku:
                            cur.execute(
                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                                (alt,),
                            )
                            rows = cur.fetchall()
                    if not rows and sku and any(sku.upper().startswith(p) for p in ("EL", "CLM", "LPU", "SIG")):
                        cur.execute(
                            'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                            'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                            ("QS_" + sku,),
                        )
                        rows = cur.fetchall()
                    if not rows and nazwa and "retro" in nazwa.lower() and "mosiądz" in nazwa.lower() and sku == "1711":
                        cur.execute(
                            'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                            'FROM products WHERE LOWER("SKU") LIKE %s AND LOWER("Nazwa") LIKE %s',
                            ("%1711%", "%retro%mosiądz%"),
                        )
                        rows = cur.fetchall()
                    if not rows and len(sku) > 1 and sku[0] == "I" and sku[1] != "I":
                        cur.execute(
                            'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                            'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                            (sku[1:],),
                        )
                        rows = cur.fetchall()
                    if not rows and sku:
                        alt = None
                        if "biały" in sku.lower():
                            alt = sku.lower().replace("biały", "b").replace("biały", "b").strip()
                        elif "czarny" in sku.lower():
                            alt = sku.lower().replace("czarny", "cz").replace("czarny", "cz").strip()
                        if alt and alt != sku.lower():
                            cur.execute(
                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                                (alt,),
                            )
                            rows = cur.fetchall()
                    if not rows and len(sku) > 2 and sku[:2] == "II":
                        for alt in (sku[1:], sku[2:]):
                            cur.execute(
                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                'FROM products WHERE LOWER(TRIM("SKU")) = LOWER(TRIM(%s))',
                                (alt,),
                            )
                            rows = cur.fetchall()
                            if rows:
                                break

                    if not rows and nazwa:
                        if "grzałka" in nazwa.lower() and "deco" in nazwa.lower():
                            for deco_num in ("2", "3", "1"):
                                if "deco " + deco_num in nazwa.lower():
                                    for p in ("l", "p"):
                                        if "grzałka " + p in nazwa.lower() or "grzałka " + p.upper() in nazwa:
                                            cur.execute(
                                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                                'FROM products WHERE LOWER("Nazwa") LIKE %s AND LOWER("Nazwa") LIKE %s',
                                                ("%deco " + deco_num + "%", "%grzałka " + p + "%"),
                                            )
                                            rows = cur.fetchall()
                                            break
                                    break
                        if not rows:
                            cur.execute(
                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                'FROM products WHERE LOWER("Nazwa") LIKE LOWER(%s)',
                                ("%" + nazwa[:50] + "%",),
                            )
                            rows = cur.fetchall()
                            if len(rows) > 1:
                                cur.execute(
                                    'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                    'FROM products WHERE LOWER("Nazwa") = LOWER(%s)',
                                    (nazwa,),
                                )
                                rows = cur.fetchall()
                    if not rows and nazwa and sku and "x" in sku.lower() and any(c.isdigit() for c in sku):
                        prod = (item.get("producent") or "").lower()
                        if "gamrat" in prod or "gamrat" in nazwa.lower():
                            cur.execute(
                                'SELECT id, "ID_produktu", "EAN", "SKU", "Nazwa", "Nazwa_producenta" '
                                'FROM products WHERE LOWER("Nazwa") LIKE %s AND LOWER("Nazwa") LIKE %s',
                                ("%gamrat%", "%orzech%"),
                            )
                            rows = cur.fetchall()
                            if len(rows) > 1 and sku.replace("x", "").replace(".", "").replace(" ", "").isdigit():
                                dim = sku.replace(" ", "")
                                rows = [r for r in rows if dim in (r[4] or "").replace(" ", "")]

                if not rows:
                    not_found.append({**item, "reason": "sku_nazwa_not_found"})
                    continue

                rows = _pick_best_row(rows, item, ean)
                if len(rows) > 1:
                    nazwa_db_set = {(r[4] or "").strip().lower() for r in rows}
                    if len(nazwa_db_set) == 1:
                        rows = [rows[0]]
                    elif len(set((r[3] or "").strip().lower() for r in rows)) == 1:
                        rows = [rows[0]]
                    elif len(rows) == 2 and "retro" in (item.get("nazwa") or "").lower():
                        by_len = sorted(rows, key=lambda r: len(r[4] or ""))
                        if by_len[0][4] != by_len[1][4]:
                            rows = [by_len[0]]
                    elif "grzałka" not in (item.get("nazwa") or "").lower():
                        base = [r for r in rows if "grzałka" not in (r[4] or "").lower()]
                        if len(base) == 1:
                            rows = base
                        else:
                            multi.append({**item, "matches": len(rows)})
                            continue
                    else:
                        multi.append({**item, "matches": len(rows)})
                        continue

                row_id, id_produktu, old_ean, sku_db, nazwa_db, prod_db = rows[0]
                if (old_ean or "").strip() == ean:
                    skipped_same += 1
                    continue

                ok = update_product(conn, row_id, "EAN", ean)
                if ok:
                    try:
                        id_prod_int = int(id_produktu) if id_produktu is not None else 0
                    except (TypeError, ValueError):
                        id_prod_int = 0
                    try:
                        insert_change_log(conn, "Arek+Ewa (batch_ean)", id_prod_int, "EAN", ean)
                    except Exception:
                        pass
                    updated += 1
                else:
                    not_found.append({**item, "reason": "update_failed"})

    print("Zaktualizowane EAN:", updated)
    print("Pominięte (już ten sam EAN):", skipped_same)
    print("Nie zaktualizowane:", len(not_found))

    if not_found:
        for x in not_found:
            r = x.get("reason", "")
            print(f"  - {r}: {x.get('nazwa', '')[:50]}... | {x.get('model_kod')} | {x.get('ean', '')[:13]}")

    if multi:
        print("Multi (nie zmieniono):", len(multi))
        for x in multi:
            print(f"  - {x.get('nazwa', '')[:50]}...")

    if no_ean:
        print()
        print(f"Bez EAN ({len(no_ean)} rekordów) – uzupełnij i wklej jako JSON z polami: nazwa, model_kod, ean, producent")


if __name__ == "__main__":
    main()
