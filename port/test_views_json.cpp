#include <assert.h>
#include <stdio.h>
#include "../source/api/views_json.h"
#include "../source/api/bootstrap_retry.h"
int main(){
    assert(jf_bootstrap_fallback(404) && jf_bootstrap_fallback(405));
    assert(!jf_bootstrap_fallback(401) && !jf_bootstrap_fallback(403));
    assert(!jf_bootstrap_fallback(503) && !jf_bootstrap_fallback(200));
    assert(jf_bootstrap_retryable(-1) && jf_bootstrap_retryable(408));
    assert(jf_bootstrap_retryable(429) && jf_bootstrap_retryable(502));
    assert(jf_bootstrap_retryable(503) && jf_bootstrap_retryable(504));
    assert(!jf_bootstrap_retryable(400) && !jf_bootstrap_retryable(401));
    assert(!jf_bootstrap_retryable(403) && !jf_bootstrap_retryable(404));
    assert(!jf_bootstrap_retryable(405) && !jf_bootstrap_retryable(200));
    const char *formatted=R"JSON(
      { "Other":{"Items":[{"Id":"wrong"}]}, "Items" : [
         {"Id":"abc","Name":"Live TV","CollectionType":"livetv",
          "Extra":{"Id":"nested","CollectionType":"movies"}},
         {"Name":"Cinema \"HD\"","CollectionType":"movies","Id":"def"}
      ], "TotalRecordCount":2 }
    )JSON";
    ViewsCursor c;ViewFields row;
    assert(views_begin(formatted,&c));
    assert(views_next(&c,&row)==1&&!strcmp(row.id,"abc")&&!strcmp(row.collection_type,"livetv"));
    assert(views_next(&c,&row)==1&&!strcmp(row.name,"Cinema \"HD\"")&&!strcmp(row.id,"def"));
    assert(views_next(&c,&row)==0);
    assert(views_begin("{\"Items\":[]}",&c)&&views_next(&c,&row)==0);
    assert(!views_begin("{\"Nested\":{\"Items\":[]}}",&c));
    assert(!views_begin("{\"Items\":{}}",&c));
    assert(!views_begin("{\"Items\":[{}",&c));
    assert(views_begin("{\"Items\":[{},]}",&c)&&views_next(&c,&row)==1&&views_next(&c,&row)==-1);
    assert(views_begin("{\"Items\":[{},42]}",&c)&&views_next(&c,&row)==1&&views_next(&c,&row)==-1);
    puts("Library catalogue whitespace, nested keys and malformed row checks passed");
}
