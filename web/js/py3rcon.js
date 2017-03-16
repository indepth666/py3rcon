new Vue({
    el: '#player',
    data: {
        players: []
    },

    mounted: function(){
        var vm = this;
        $.getJSON('/action/getplayers', function (data) {
            vm.players = data;
        });
    },
    methods: {
        Kick: function(item){
            var vm = this;
            console.log(item);
            $.post('/action/kickplayer', { id: item.number }, function (data) {
                var index = vm.players.indexOf(item);
                vm.players.splice(index, 1);
            });
        }
    }
})