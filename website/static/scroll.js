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
    var dud = document.getElementById("dudley");
    nav.classList.toggle("hide");
    content.classList.toggle("exp");
    head.classList.toggle("exp");
    arr.classList.toggle("adjustarrow");
    tog.classList.toggle("tcolor");
    dud.classList.toggle("show");
  }


const hiddenElements = document.querySelectorAll('.hidden');
const hiddenyElements = document.querySelectorAll('.hiddeny');
const hiddenuElements = document.querySelectorAll('.hiddenu');
const hiddenzElements = document.querySelectorAll('.hiddenz');
hiddenElements.forEach((el) => observer.observe(el));
hiddenyElements.forEach((el) => observer.observe(el));
hiddenuElements.forEach((el) => observer.observe(el));
hiddenzElements.forEach((el) => observer.observe(el));