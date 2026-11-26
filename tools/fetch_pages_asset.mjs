// Public static assets only; no credentials, cookies or private network access.
const [target, size] = process.argv.slice(2);
const limit=Number(size), u=new URL(target);
if(u.origin!=="https://jealouswin.pages.dev" || !u.pathname.startsWith("/jellop-test/v1/") ||
   !Number.isSafeInteger(limit)||limit<1||limit>4*1024*1024) throw new Error("Invalid fixture request");
const response=await fetch(u,{redirect:"error",signal:AbortSignal.timeout(30000)});
if(!response.ok){
    console.error("HTTP",response.status,"content-type",response.headers.get("content-type"),"server",response.headers.get("server"));
    process.exit(1);
}
if(!response.body)throw new Error("Empty response body");
const chunks=[];let total=0;
for await(const chunk of response.body){
    total+=chunk.length;
    if(total>limit)throw new Error("Asset exceeds bound");
    chunks.push(chunk);
}
process.stdout.write(Buffer.concat(chunks,total));
