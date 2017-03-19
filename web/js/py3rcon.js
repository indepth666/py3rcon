var AlertVue = new Vue({
    el: '#alert',
    data: {
        message: '',
        type: '',
        visible: false,
        allowClose: false
    },
    methods: {
        Show: function(msg, t, closeable){
            this.message = msg;
            this.type = t;
            this.visible = true;
            this.allowClose = closeable;
        },
        Hide: function(){
            this.message = '';
            this.visible = false;
        }
    }
});

var playerVue = new Vue({
    el: '#player',
    data: {
        players: [],
    },
    mounted: function(){
        this.Load();
    },
    methods: {
        Load: function(){
            var vm = this;
            AlertVue.Show('Loading...', 'alert-info');
            $.getJSON('/action/players', function (data) {
                vm.players = data;
                AlertVue.Hide();
            });
        },
        Restart: function(){
            $.post('/action/restart', null, function(){
                AlertVue.Show('Restart takes action...', 'alert-info');
            });
        },
        Shutdown: function(){
            $.post('/action/shutdown', null, function(){
                AlertVue.Show('Shutdown takes action...', 'alert-info');
            });
        },
        Kick: function(item, ban){
            var vm = this;

            console.log(item);
            $.post('/action/kickplayer', { id: item.number, ban: ban }, function (data) {
                var index = vm.players.indexOf(item);
                vm.players.splice(index, 1);
            });
        }
    }
})