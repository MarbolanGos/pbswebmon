function alternate(id){
	if(document.getElementsByTagName){
		var table = document.getElementById(id);
		var rows = table.getElementsByTagName("tr");
		for(i = 0; i < rows.length; i++){
			//manipulate rows
			rows[i].className = (i % 2 == 0) ? rows[i].className = "even" : rows[i].className = "odd";
		}
	}
}
