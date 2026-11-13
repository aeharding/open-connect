// Execute the actual private OEM dispatcher, with the candidate context callback.
const fs=require('fs'), vm=require('vm'), assert=require('assert/strict');
const [candidate,base]=process.argv.slice(2);
const events=[];
const sandbox={log:{addSrcFile(){},error(e){throw Error(e)},writeError(e){throw e}},
 framework:{sendEventToMmui(...a){events.push(a)}}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(base,'utf8'),sandbox);
const source=fs.readFileSync(candidate,'utf8');
const start=source.indexOf('"IntroAnimation" : {');
const stop=source.indexOf('"QuickStartLoop" : {',start);
const literal='({'+source.slice(start,stop)+'})';
function app(next,lost=false){
 const a={uiaId:'system',_currentContext:{ctxtId:lost?'IntroAnimation':next},
  _outgoingContext:lost?null:{ctxtId:'IntroAnimation'},_outgoingContextTemplate:lost?null:{},
  _currentContextTemplate:{}};
 sandbox.app=a;a._contextTable=vm.runInContext('(function(){return '+literal+'}).call(app)',sandbox);
 a._contextTable.HomeScreen={};a._contextTable.Disclaimer={};
 return a;
}
for(const next of ['HomeScreen','Disclaimer']){
 events.length=0;const a=app(next),t=a._outgoingContextTemplate;
 assert.equal(events.length,0); // constructing/readying never disposes
 sandbox.BaseApp.prototype._templateNoLongerDisplayed.call(a,t);
 assert.equal(events.length,next==='Disclaimer'?0:1);
 if(events.length)assert.deepEqual(events[0],['system','DisposeIntroVideo']);
 assert.equal(a._outgoingContext,null);
 // OEM clears outgoing ownership: duplicate notification cannot dispatch again.
 sandbox.BaseApp.prototype._templateNoLongerDisplayed.call(a,t);
 assert.equal(events.length,next==='Disclaimer'?0:1);
}
events.length=0;const lost=app(null,true);
sandbox.BaseApp.prototype._templateNoLongerDisplayed.call(lost,lost._currentContextTemplate);
assert.deepEqual(events,[['system','DisposeIntroVideo']]);
assert.equal(lost._currentContextTemplate,null);
console.log('PASS actual OEM lifecycle: no early disposal, native completion event once, stock Disclaimer owns its cleanup, lost-focus cleanup');
