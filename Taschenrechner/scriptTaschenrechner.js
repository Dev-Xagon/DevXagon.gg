const ersteNummerInput= document.getElementById('ersteNummer'); //undefined
const zweiteNummerInput= document.getElementById('zweiteNummer'); //undefined
const operatorSelectInput=document.getElementById('operator');
const berechnenButton= document.getElementById('berechnen');
const resultatParagraph=document.getElementById('Resultat');

const resultatOnImage=document.getElementById("resultatOnImage");

let resultat;


function berechnen()
{
const ersteNummer = parseFloat(ersteNummerInput.value);
const zweiteNummer= parseFloat(zweiteNummerInput.value);
const operator =operatorSelectInput.value;

let resultat;

switch(operator) {
    case "+":
        resultat = ersteNummer + zweiteNummer;
        break;
    case "-":
        resultat = ersteNummer - zweiteNummer;
        break;
    case "*":
        resultat = ersteNummer * zweiteNummer;
        break;
    case "/":
        resultat = zweiteNummer !== 0 ? ersteNummer / zweiteNummer : "Durch 0 kann nicht geteilt werden!";
        break;
    default:
        resultat = "Ungültiger Operator";
}
resultatParagraph.textContent ='Ergebnis: ' + resultat;

resultatOnImage.textContent= resultat;
}


berechnenButton.addEventListener('click', berechnen);
