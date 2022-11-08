const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        console.log(entry)
        if (entry.isIntersecting) {
            entry.target.classList.add('show');
        } else{
            entry.target.classList.remove('show');
        }
    });
});
function toggleNav() {
    var nav = document.getElementById("subnav");
    var content = document.getElementById("cont");
    var head = document.getElementById("hed");
    var arr = document.getElementById("arr");
    var tog = document.getElementById("toggler");
    //var home = document.getElementById("col-sm-12");
    //var foot = document.getElementById("foot");
    nav.classList.toggle("hide");
    content.classList.toggle("exp");
    head.classList.toggle("exp");
    arr.classList.toggle("adjustarrow");
    tog.classList.toggle("tcolor");
    //home.classList.toggle("exp");
    //foot.classList.toggle("exp");
  }


const hiddenElements = document.querySelectorAll('.hidden');
hiddenElements.forEach((el) => observer.observe(el));