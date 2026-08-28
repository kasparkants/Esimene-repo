#Ülesanne 3 Inimese kehaanalüüs
#Uurime inimest. Tundide tabelis on link valemitele, mille abil saab leida inimese
#ideaalkaalu, rasvaprotsendi, tiheduse, ruumala ja pindala.

#Kontrollimiseks testandmed:

#kaal: 75
#pikkus: 178
#vanus: 22
#-------------------
#ideaalkaal  mehele: 71.50   naisele: 64.35
#rasvasuse % mehele: 19.67   naisele: 36.20
#tihedus     mehele: 1058.70   naisele: 1023.98
#ruumala     mehele: 0.071   naisele: 0.073
#pindala     mehele: 1.929   naisele: 1.929

import math
#lisan import math, et saaksin hiljem kasutada math.log funktsiooni

#ANDMED
height = float(input("kui pikk on inimene?"))
weight = float(input("kui palju kaalub inimene?"))
age = float(input("kui vana on inimene?"))
gender = float(input("mis on inimese sugu? (1-mees ja 2-naine)"))
#Paremat viisi ei oska veel kui teha nii, et mees on üks arv ja naine teine arv :)

#Püüdsin if variable'i kasutada, ja see variant tundus okei praeguste oskustega.
#Kui soo määraja on alla 2'e, siis on tegu mehe andmetega, naise andmed saab else rakendamisel kätte)
if gender < 2:
    idealweight = ((3 * height - 450 + age) * 0.25 + 45)
    print("Ideaalkaal on", idealweight, "kg")
else:
    idealweight = ((3 * height - 450 + age) * 0.225 + 40.5)
    print("Ideaalkaal on", idealweight, "kg")

if gender < 2:
    bodyfat = (((weight - idealweight) / weight) * 100 + 15)
    print("Rasvaprotsent on", bodyfat, "%")
else:
    bodyfat = (((weight - idealweight) / weight) * 100 + 22)
    print("Rasvaprotsent on", bodyfat, "%")
    
density = ((8.9 * bodyfat) + 11 * (100 - bodyfat))
print("Tihedus on", density, "kg/m³")

volume = (weight / density)
print("Ruumala on", volume, "m³")

area = ((1000 * weight) ** ((35.75 - math.log10(weight)) / 53.2) * ((height ** 0.3) / 3118.2))
print("Pindala on", area, "m²")