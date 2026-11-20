const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('templates/index.html','utf8');
function extract(start,end) {
 const first=html.indexOf(start);
 if(first<0)throw Error('Missing function '+start);
 const last=html.indexOf(end, first + start.length);
 if(last<0)throw Error('Missing ending '+end);
 return html.slice(first,last);
}
const elements = {
 'pf-personalize-setup-add-select': {value:'raspberry',focus(){}},
 'pf-personalize-setup-add-amount-row': {hidden:true},
 'pf-personalize-setup-add-amount': {value:'',placeholder:'',focus(){this.focused=true}},
 'pf-personalize-setup-add-amount-unit': {textContent:''},
 'pf-personalize-setup-add-amount-note': {textContent:''},
 'pf-personalize-setup-status': {textContent:''},
};
let added=[];let refreshed=0;
const context = {
 document:{getElementById:(id)=>elements[id]||null},
 pfPersonalizeIngredientOptions:[
  {id:'raspberry', display_name:'Raspberry',amount:70,amount_source:'same_goal_reviewed_recipe_component',unit:'g'},
  {id:'almond-milk', display_name:'Almond Milk',amount:150,amount_source:'current_reviewed_recipe_component',unit:'ml'},
  {id:'unreviewed', display_name:'Unreviewed',amount:null,amount_source:'manual_amount_required',unit:'g'},
  {id:'clementine', display_name:'Clementine',amount:75,amount_source:'usda_standard_portion',amount_label:'1 fruit',unit:'g'},
 ],
 pfPersonalizeCatalogMode:'all-supported',
 pfPersonalizeGoalAlignedIngredientIds:new Set(['raspberry']),
 pfAppendPersonalizeSetupIngredient:(x)=>added.push(x),
 pfRefreshPersonalizeSetupControls:()=>refreshed++,
};
vm.createContext(context);
vm.runInContext(extract('function pfSyncPersonalizeAdditionAmount()', 'function pfRefreshPersonalizeSetupControls()') + extract('function pfAddPersonalizeSetupIngredient()', 'function pfLoadPersonalizeIngredientOptions()'), context);
context.pfSyncPersonalizeAdditionAmount();
if(elements['pf-personalize-setup-add-amount'].value!=='70')throw Error('Raspberry amount not initialized');
context.pfAddPersonalizeSetupIngredient();
if(added.length!==1||added[0].amount!==70)throw Error('Raspberry amount not added');
elements['pf-personalize-setup-add-select'].value='almond-milk';context.pfSyncPersonalizeAdditionAmount();
if(elements['pf-personalize-setup-add-amount-unit'].textContent!=='mL')throw Error('mL unit not set');
elements['pf-personalize-setup-add-amount'].value='105';context.pfAddPersonalizeSetupIngredient();
if(added.length!==2||added[1].amount!==105)throw Error('Manual amount not honored');
elements['pf-personalize-setup-add-select'].value='unreviewed';context.pfSyncPersonalizeAdditionAmount();
if(elements['pf-personalize-setup-add-amount'].value!=='')throw Error('Unreviewed value fabricated');
context.pfAddPersonalizeSetupIngredient();
if(added.length!==2)throw Error('Blank unreviewed amount allowed');
elements['pf-personalize-setup-add-amount'].value='25';context.pfAddPersonalizeSetupIngredient();
if(added.length!==3 || added[2].amount!==25)throw Error('Manual-only selection not accepted');
elements['pf-personalize-setup-add-select'].value='clementine';context.pfSyncPersonalizeAdditionAmount();
if(elements['pf-personalize-setup-add-amount'].value!=='75')throw Error('USDA portion not initialized');
if(!elements['pf-personalize-setup-add-amount-note'].textContent.includes('USDA standard portion (1 fruit)'))throw Error('USDA note missing');
console.log('PASS — JS auto-fill g/mL; editable quantities; manual-only validation; no blank inserted');
