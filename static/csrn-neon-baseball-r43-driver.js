(() => {
"use strict";
const VERSION="1.0.0-r43a";
const base=window.CSRNNeonR2Engine;
if(!base)throw new Error("Baseball R43 requires the frozen Neon R2 engine and preceding supplemental drivers.");
function baseballLayers(){
  return `<div class="n2-baseball-r43 home-color"></div><div class="n2-baseball-r43 visitor-color"></div><div class="n2-baseball-r43 scene"></div><div class="n2-baseball-r43 home-texture"></div><div class="n2-baseball-r43 visitor-texture"></div>`;
}
function renderPackage(root,id,sport="football",value={},options={}){
  const result=base.renderPackage(root,id,sport,value,options);
  if(sport!=="baseball")return result;
  const opening=root?.querySelector?.(".n2-opening");
  if(!opening)return result;
  opening.querySelectorAll(":scope > .n2-action").forEach(node=>node.remove());
  const template=document.createElement("template");
  template.innerHTML=baseballLayers();
  opening.prepend(template.content);
  root.dataset.baseballDriverVersion=VERSION;
  return result;
}
window.CSRNNeonBaseballR43Driver=Object.freeze({version:VERSION,renderPackage});
window.CSRNNeonR2Engine=Object.freeze({...base,renderPackage});
})();
