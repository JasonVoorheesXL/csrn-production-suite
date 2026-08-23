(() => {
"use strict";
const VERSION="1.0.0-r42a";
const base=window.CSRNNeonR2Engine;
if(!base)throw new Error("Softball R42 requires the frozen Neon R2 engine.");
function softballLayers(){
  return `<div class="n2-softball-r42 home-color"></div><div class="n2-softball-r42 visitor-color"></div><div class="n2-softball-r42 scene"></div><div class="n2-softball-r42 home-texture"></div><div class="n2-softball-r42 visitor-texture"></div>`;
}
function renderPackage(root,id,sport="football",value={},options={}){
  const result=base.renderPackage(root,id,sport,value,options);
  if(sport!=="softball")return result;
  const opening=root?.querySelector?.(".n2-opening");
  if(!opening)return result;
  opening.querySelectorAll(":scope > .n2-action").forEach(node=>node.remove());
  const template=document.createElement("template");
  template.innerHTML=softballLayers();
  opening.prepend(template.content);
  root.dataset.softballDriverVersion=VERSION;
  return result;
}
window.CSRNNeonSoftballR42Driver=Object.freeze({version:VERSION,renderPackage});
window.CSRNNeonR2Engine=Object.freeze({...base,renderPackage});
})();
