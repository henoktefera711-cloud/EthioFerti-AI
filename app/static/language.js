(()=>{
"use strict";
const translations={
"EthioFerti AI · Material Intelligence":"EthioFerti AI · የግብዓት ብልህ ስርዓት",
"EthioFerti AI · Product Information":"EthioFerti AI · የምርት መረጃ",
"EthioFerti AI · QR Verification":"EthioFerti AI · የQR ማረጋገጫ",
"EthioFerti AI — Projects":"EthioFerti AI — ፕሮጀክቶች",
"AI Material Scan":"የግብዓት AI ምርመራ",
"QR Scan":"የQR ስካን",
"Open camera":"ካሜራ ክፈት",
"Capture and analyze":"ፎቶ አንሳ እና መርምር",
"Stop camera":"ካሜራ አቁም",
"Retry pending AI analyses":"ያልተጠናቀቁ የAI ምርመራዎችን እንደገና ሞክር",
"AI Camera Projects":"የAI ካሜራ ፕሮጀክቶች",
"Preparing local database...":"የአካባቢ ዳታቤዝ በመዘጋጀት ላይ...",
"Loading AI projects...":"የAI ፕሮጀክቶችን በመጫን ላይ...",
"Ready to scan.":"ስካን ለማድረግ ዝግጁ ነው።",
"QR Scan Projects":"የQR ስካን ፕሮጀክቶች",
"Loading QR projects...":"የQR ፕሮጀክቶችን በመጫን ላይ...",
"AI Inspection Details":"የAI ምርመራ ዝርዝሮች",
"Paste QR data or product token":"የQR ዳታ ወይም የምርት መለያ አስገባ",
"Read product information":"የምርት መረጃ አንብብ",
"▧ Upload QR image from device":"▧ ከስልክ የQR ምስል ምረጥ",
"Camera stopped.":"ካሜራው ቆሟል።",
"Camera ready. Point it at the actual fertilizer material.":"ካሜራው ዝግጁ ነው። ካሜራውን በትክክለኛው የማዳበሪያ ቁሳቁስ ላይ አቅና።",
"Camera requires HTTPS or localhost.":"ካሜራውን ለመጠቀም HTTPS ወይም localhost ያስፈልጋል።",
"Camera is not ready.":"ካሜራው ገና ዝግጁ አይደለም።",
"Camera ready.":"ካሜራው ዝግጁ ነው።",
"Camera error:":"የካሜራ ስህተት፦",
"Capture and analyze":"ፎቶ አንሳ እና መርምር",
"Saving photograph...":"ፎቶውን በማስቀመጥ ላይ...",
"Inspecting...":"በመመርመር ላይ...",
"Analyze fertilizer material":"የማዳበሪያ ቁሳቁሱን መርምር",
"Photograph saved locally. Checking its visible features on this device...":"ፎቶው በስልኩ ላይ ተቀምጧል። የሚታዩ ባህሪያቱ በዚህ መሣሪያ ላይ እየተመረመሩ ነው...",
"Offline mode. Local photograph storage is ready.":"ከኢንተርኔት ውጭ ነው። ፎቶዎችን በስልኩ ላይ ማስቀመጥ ይቻላል።",
"Local database ready. Camera inspection is available.":"የአካባቢ ዳታቤዝ ዝግጁ ነው። የካሜራ ምርመራ ይቻላል።",
"Local database error:":"የአካባቢ ዳታቤዝ ስህተት፦",
"Analysis result":"የምርመራ ውጤት",
"Observed physical characteristics":"የታዩ አካላዊ ባህሪያት",
"Fertilizer identified":"ማዳበሪያው ተለይቷል",
"Possible fertilizer match":"ሊሆን የሚችል የማዳበሪያ ተመሳሳይነት",
"Material analysis":"የቁሳቁስ ምርመራ",
"Fertilizer":"ማዳበሪያ",
"Nutrient grade":"የንጥረ ነገር ደረጃ",
"Fertilizer type":"የማዳበሪያ ዓይነት",
"Composition":"ይዘት",
"Suitable crops":"ተስማሚ ሰብሎች",
"Agricultural uses":"የግብርና አጠቃቀሞች",
"Match confidence":"የመለየት እርግጠኝነት",
"Result":"ውጤት",
"This photograph was rejected.":"ይህ ፎቶ ለምርመራ ተቀባይነት አላገኘም።",
"The material could not be identified confidently from this photograph.":"ቁሳቁሱን ከዚህ ፎቶ በበቂ እርግጠኝነት መለየት አልተቻለም።",
"View full fertilizer profile":"ሙሉ የማዳበሪያ መረጃ ተመልከት",
"Close":"ዝጋ",
"Fertilizer details":"የማዳበሪያ ዝርዝር መረጃ",
"Chemical name":"የኬሚካል ስም",
"Chemical formula":"የኬሚካል ቀመር",
"Fertilizer classification":"የማዳበሪያ ምድብ",
"Nutrient composition":"የንጥረ ነገሮች ይዘት",
"What the nutrients do":"የንጥረ ነገሮቹ ጥቅም",
"About this fertilizer":"ስለዚህ ማዳበሪያ",
"Physical forms":"አካላዊ ቅርጾች",
"Soil considerations":"የአፈር ግምት ነገሮች",
"Application guidance":"የአጠቃቀም መመሪያ",
"Application methods":"የመተግበሪያ ዘዴዎች",
"Compatibility":"ተስማሚነት",
"Nutrient deficiency information":"የንጥረ ነገር እጥረት መረጃ",
"Nutrient deficiency indicators":"የንጥረ ነገር እጥረት ምልክቶች",
"Excess and risk information":"ከመጠን በላይ መጠቀምና አደጋዎች",
"Storage":"አከማቻ",
"Verification information":"የማረጋገጫ መረጃ",
"Sources":"ምንጮች",
"Product name":"የምርት ስም",
"Category":"ምድብ",
"Batch code":"የሎት መለያ",
"Quantity (kg)":"መጠን (ኪ.ግ)",
"QR code type":"የQR ኮድ ዓይነት",
"QR link":"የQR አገናኝ",
"Manufacturer":"አምራች",
"Origin":"የትውልድ ቦታ",
"Registration number":"የምዝገባ ቁጥር",
"Production date":"የምርት ቀን",
"Expiry date":"የማብቂያ ቀን",
"Description":"መግለጫ",
"Ingredients":"ጥሬ ዕቃዎች",
"Benefits":"ጥቅሞች",
"Application instructions":"የአጠቃቀም መመሪያ",
"Safety instructions":"የደህንነት መመሪያ",
"Storage instructions":"የማከማቻ መመሪያ",
"Enter QR data or a product token, or use the camera or image upload.":"የQR ዳታ ወይም የምርት መለያ አስገባ፤ ወይም ካሜራውን ተጠቀም።",
"Reading QR code...":"QR ኮዱን በማንበብ ላይ...",
"Start QR camera":"የQR ካሜራ ክፈት",
"Camera active. Hold the QR code steady.":"ካሜራው እየሰራ ነው። QR ኮዱን እንዳይንቀሳቀስ ያዝ።",
"Camera active. Hold the QR code steady inside the camera view.":"ካሜራው እየሰራ ነው። QR ኮዱን በካሜራው እይታ ውስጥ በጥንቃቄ ያዝ።",
"Camera stopped.":"ካሜራው ቆሟል።",
"Enter QR data or a product token.":"የQR ዳታ ወይም የምርት መለያ አስገባ።",
"QR data is empty.":"የQR ዳታው ባዶ ነው።",
"QR code detected. Opening product information...":"QR ኮዱ ተገኝቷል። የምርት መረጃ በመክፈት ላይ...",
"Open product information":"የምርት መረጃ ክፈት",
"Scan product QR code":"የምርት QR ኮድ ስካን አድርግ",
"Enter QR data or token":"የQR ዳታ ወይም መለያ አስገባ",
"Back to dashboard":"ወደ ዋና ገጽ ተመለስ",
"Scan another QR code":"ሌላ QR ኮድ ስካን አድርግ",
"Product Information":"የምርት መረጃ",
"Reading QR code...":"QR ኮዱን በማንበብ ላይ...",
"Loading product information.":"የምርት መረጃን በመጫን ላይ...",
"Product information":"የምርት መረጃ",
"Product not available offline":"ምርቱ ከኢንተርኔት ውጭ አይገኝም",
"QR data could not be read":"የQR ዳታውን ማንበብ አልተቻለም",
"Product lookup failed":"የምርት ፍለጋ አልተሳካም",
"Registered product":"የተመዘገበ ምርት",
"Product record found in this device's local database.":"የምርቱ መዝገብ በዚህ መሣሪያ የአካባቢ ዳታቤዝ ውስጥ ተገኝቷል።",
"QR Verification":"የQR ማረጋገጫ",
"Paste EF1: data or legacy QR token":"EF1: ዳታ ወይም የቀድሞ QR መለያ አስገባ",
"Local database ready. Camera inspection is available.":"የአካባቢ ዳታቤዝ ዝግጁ ነው። የካሜራ ምርመራ ይቻላል።"
};
const prefixes=[
["Camera error:","የካሜራ ስህተት፦"],
["Local database error:","የአካባቢ ዳታቤዝ ስህተት፦"],
["Material inspection error:","የቁሳቁስ ምርመራ ስህተት፦"],
["Recognition error:","የመለየት ስህተት፦"],
["Image scan error:","የምስል ስካን ስህተት፦"],
["QR reading error:","የQR ንባብ ስህተት፦"],
["QR verification failed:","የQR ማረጋገጫ አልተሳካም፦"],
["Project history error:","የፕሮጀክት ታሪክ ስህተት፦"],
["History error:","የታሪክ ስህተት፦"]
];
const key="ethioferti-language";
let language="am";
try{language=localStorage.getItem(key)||"am";}catch{}
const originals=new WeakMap();
function translateNode(node){
 if(node.nodeType===3){
  const source=originals.has(node)?originals.get(node):node.nodeValue;
  if(!originals.has(node))originals.set(node,source);
  const trimmed=source.trim();
  if(!trimmed)return;
  let result=language==="am"?(translations[trimmed]||trimmed):trimmed;
  if(language==="am"&&!translations[trimmed]){
   for(const [prefix,am] of prefixes){
    if(trimmed.startsWith(prefix)){result=am+trimmed.slice(prefix.length);break;}
   }
  }
  const nextValue=source.replace(trimmed,result);
  if(node.nodeValue!==nextValue)node.nodeValue=nextValue;
 }else if(node.nodeType===1){
  for(const attr of ["placeholder","title","aria-label"]){
   if(node.hasAttribute(attr)){
    const source=node.getAttribute("data-language-original-"+attr)||node.getAttribute(attr);
    if(!node.hasAttribute("data-language-original-"+attr))node.setAttribute("data-language-original-"+attr,source);
    node.setAttribute(attr,language==="am"?(translations[source]||source):source);
   }
  }
  if(node.childNodes)node.childNodes.forEach(translateNode);
 }
}
function apply(){
 document.documentElement.lang=language;
 document.documentElement.style.fontFamily=language==="am"?"'Noto Sans Ethiopic','Nyala','Abyssinica SIL',Arial,sans-serif":"Inter,'Segoe UI',Roboto,Arial,sans-serif";
 translateNode(document.body);
 const button=document.getElementById("ethiofertiLanguageToggle");
 if(button){
  button.textContent=language==="am"?"English":"አማርኛ";
  button.title=language==="am"?"Switch to English":"ወደ አማርኛ ቀይር";
  button.setAttribute("aria-label",button.title);
 }
}
function init(){
 const header=document.querySelector("header");
 if(header&&!document.getElementById("ethiofertiLanguageToggle")){
  const button=document.createElement("button");
  button.id="ethiofertiLanguageToggle";
  button.type="button";
  button.style.cssText="position:absolute;right:14px;top:50%;transform:translateY(-50%);z-index:5;background:#ffffff20;color:white;border:1px solid #ffffff65;border-radius:10px;padding:9px 13px;font-size:13px;font-weight:800;min-width:76px";
  button.addEventListener("click",()=>{
   language=language==="am"?"en":"am";
   try{localStorage.setItem(key,language);}catch{}
   apply();
  });
  header.append(button);
  header.style.paddingRight="105px";
  header.style.position="relative";
 }
 apply();
 const observer=new MutationObserver(records=>{
  for(const record of records){
   if(record.type==="characterData")translateNode(record.target);
   else record.addedNodes.forEach(translateNode);
  }
 });
 observer.observe(document.body,{subtree:true,childList:true,characterData:true});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
else init();
})();
