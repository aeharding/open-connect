// Minimal DOM surface shared by offline UI fixtures; animation delivery is explicit.
module.exports=function element(parent=null) {
    if(parent&&!parent.appendChild)parent.appendChild=function(n){n.parentNode=this;};
    const listeners=new Map(),classes=new Set();
    return {parentNode:parent,style:{display:""},classes,listeners,
        classList:{add(c){classes.add(c);},remove(c){classes.delete(c);}},
        addEventListener(k,f){if(!listeners.has(k))listeners.set(k,new Set());listeners.get(k).add(f);},
        removeEventListener(k,f){listeners.get(k)?.delete(f);},
        emit(k,event={}){for(const f of [...(listeners.get(k)||[])])f({target:this,...event});}
    };
};
