mylist=["Nutte", "Haus", "Tennisschlaeger"]
mylist.append("Hamster")
print(mylist)
#Hier jetzt selbst etwas ins Terminal schreiben
dusche=input("Waschmittel: ")
mylist.append("Dusche")
if("Dusche" in mylist):
    print("Matze ist jetzt sauber und duftet wie ein Kirschbaum")
else:
    print("stinker")
print(mylist)

print(len(mylist))
if (len(mylist)>4):
    mylist.append("Cola")
    print(mylist)