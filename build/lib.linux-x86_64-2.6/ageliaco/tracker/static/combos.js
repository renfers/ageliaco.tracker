jq(document).ready(function(){
    jq('#opened_issues').change(function(){
          jq('#draft_issues').load('combo-values?value='+this.value);
          jq('#pending_issues').load('combo-values?value='+this.value);
          jq('#closed_issues').load('combo-values?value='+this.value);
    });
});