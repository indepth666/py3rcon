/**
 * jQuery custom binding extension
 * 
 * Author: Ole Koeckemann <ole.k@web.de>
 * Requirements: jQuery jQuery.promise
 */

function CustomBind(contextName, options) {
	var self = this;
	var perf = 0;

	var evtSave = function(el, data){
		if(self.settings.debug > 0) console.log('Save event fired in ' + self.settings.contextName);
		updateDataFromControl(el, data);
	};
	var evtRender = function() {
		if(self.settings.debug > 1){
			console.log('Rendering ' + contextName + '...');
			perf = new Date().getTime();
		}

		if(self.onRender != null) self.onRender(self);
		
		if(CustomBind.$ctxLoading.settings.contextName != self.settings.contextName && self.settings.showLoading) {
			CustomBind.$ctxLoading.Load({text: 'Rendering ' + contextName}, true);
		}
	};
	var evtRenderComplete = function() {
		if(self.settings.debug > 0) {
			console.log('Rendering ' + contextName + ' complete!');
			console.log((new Date().getTime() - perf) + 'ms');
		}

		if(self.onRenderComplete != null) self.onRenderComplete(self);
		
		self.Show();

		if(CustomBind.$ctxLoading.settings.contextName != self.settings.contextName && self.settings.showLoading)
			CustomBind.$ctxLoading.Hide();
	};
	
	var defaults = { contextName: contextName, allowHide: true, hideOther: true, showLoading: true, noAsync: false,persistent: false, lifetime: 0, debug: 0, events: { } };
	var source = null;
	self.settings = {};
	
	var $context = null;
	var contextList = [];
	var crcTable = null;
	var cachedItems = {};

	this.onRender = null;
	this.onRenderComplete = null;
	this.onDataBind = function(ctx){ if(self.settings.debug > 0) console.log('Databind event not set in ' + contextName); return []; };

	var _makeCRCTable = function(){
		var c;
		var crcTable = [];
		for(var n =0; n < 256; n++){
			c = n;
			for(var k =0; k < 8; k++){
				c = ((c&1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
			}
			crcTable[n] = c;
		}
		return crcTable;
	};

	var checksum = function(str) {
			var crc = -1, i = 0
			while (i < str.length)
				crc = (crc >>> 8) ^ crcTable[(crc ^ str.charCodeAt(i++)) & 0xFF]
			return (crc ^ -1) >>> 0
	};

	var _load = function(optSource, rebind){	
		if(optSource)
			source = optSource;
		else if($.isFunction(self.onDataBind))
			source = self.onDataBind($context);
		else
			source = self.onDataBind;
					
		if(self.settings.hideOther) 
			hideOther();
		
		$.when(bindControls(), bindRepeater(rebind)).then(function(){
			evtRenderComplete();
		});
	};
	
	this.Load = function(optSource, rebind) {
		evtRender();
		
		if(self.settings.noAsync)
			_load(optSource, rebind);
		else
			setTimeout(function() { _load(optSource, rebind); }, 1);
	};

	this.GetContext = function(){
		return $context;
	};

	this.SetContext = function(ctx){
		$context = ctx;
		$context.attr('jb-context', self.settings.contextName);
	};
	
	this.Hide = function(){
		$context.hide();
	};
	
	this.Show = function(){
		$context.show();
	};

	this.UpdateData = function(oldData, newData) {
		$.each(newData, function(k, v){
			oldData[k] = newData[k];
		});
	};
	
	var hideOther = function(){
		for(var p in CustomBind.$collection) {
			var value = CustomBind.$collection[p];
			if(value.settings.contextName != contextName && value.settings.allowHide)
				value.Hide();
		}
	};
	
	var convertDots = function(v){
		var query = "";
		var res = v.split('.');
		for(var i = 0; i < res.length; i++) {
			if($.isNumeric(res[i]))
				query += '[' + res[i] + ']';
			else 
				query += '["' + res[i] + '"]';
		}
		return query;
	};
	
	var updateDataFromControl = function(el, data){
		$context.find('*[jb-bind!=""][jb-bind]').each(function(i, item){
			var $item = $(item);
			var tagName =  $item.prop('tagName');
			if(tagName == 'INPUT') {
				eval('data' + convertDots($item.attr('jb-bind')) + ' = "' + $item.val() + '"' );
			}	
		});
	};
	
	var parseCondition = function(condStr, data){
		if(!condStr) return true;
		if(!data) return true;
		// jb-show attribute - conditional display output
		var m = condStr.match(/^[\w.]+$|([\w.]+)\s+?(==|>|<|<=|>=)\s+?([\w.]+)|([\w.]+)\s+?(&|\||\^)\s+?([\w.]+)\s+?(==|!=)\s+([\w.]+)$/)
		if(m[1]) {
            // regular condition
			return eval('data' + convertDots(m[1]) + ' ' + m[2] + ' ' + m[3]);
		} else if(m[4]) {
            // bitwise condition
            return eval('(data' + convertDots(m[4]) + ' ' + m[5] + ' ' + m[6] + ') ' + m[7] + m[8]);
        } else {
            // other
            return eval('data' + convertDots(m[0]));
        }
	};
	
	var parseBindText = function(data, v){
		try{
			return eval("data" + convertDots(v));
		}
		catch(e){
			console.log('Failed to bind: ' + v);
			return "";
		}
	};
	
	var parseBindAttr = function(data, el){
		if(!el[0].attributes) return;
		$.each(el[0].attributes, function(){
			if(this.name && this.value != "" && this.value.substring(0,1) == "="){
				this.value = eval("data" + convertDots( this.value.substring(1) ));
			}
		});
	};

	var bindContext = function(ctxCopy, ctxName, data){
		if(!CustomBind.$collection.hasOwnProperty(ctxName))
			return;

		var ctxObject = CustomBind.$collection[ctxName];

		var ts = new Date().getTime();

		settings = $.extend(true, {}, ctxObject.settings);
		settings.contextName += "-" + ts;

		ctxClone = new CustomBind(settings.contextName, settings);
		ctxClone.SetContext(ctxCopy);
		// do not hide others as it is nested
		ctxClone.settings.hideOther = false;
		ctxClone.Load(data, true);
	};

	var bindControls = function(s, el, fromRepeater){
		var dfd = $.Deferred();
		
		if(!el) el = $context;
		if(!s) s = source;

		el.find('*[jb-bind]').each(function(i, item){
			var $item = $(item);

			if($item.attr('jb-render') == '2') return;
			
            // when the controls are inside a repeater, but its not called from the repeater, ignore it
            var found = $item.closest('*[jb-repeat]');
            if(found.length > 0 && typeof fromRepeater === 'undefined') return;
            
            // bindControls has been called from bindRepeater
            if(typeof fromRepeater !== 'undefined') {
                // skip nested repeaters
                if(found.length > 0 && found != fromRepeater) return;
                
                $item.attr('jb-render', '2');
            } else {
                $item.attr('jb-render', '1');
            }
                        
            // use jb-show attribute to conditionally DISPLAY this element
            var isCond = parseCondition($item.attr('jb-show'), s);
            if(!isCond) {
                $item.hide();
                return;
            }
            
            // use jb-cond attribute to conditionally BIND this element
            isCond = parseCondition($item.attr('jb-cond'), s);
            if(!isCond) {
                // do not bind the value from data source
                return;
            }

			if(s !== null) {
				var bindValue = $item.attr('jb-bind');
					var tagName =  $item.prop('tagName');
				if(tagName == 'INPUT' && bindValue)
					$item.val( parseBindText(s,bindValue) );
				else
					$item.html( parseBindText(s,bindValue) );

				parseBindAttr(s,$item);
			}
            
            // (re)bind all events
            bindEvent(item, s);
            
            // lifetime of the DOM if defined in settings
            if(self.settings.lifetime > 0) setTimeout(function(){ $item.remove() }, self.settings.lifetime);
		});
		dfd.resolve();
		return dfd.promise();
	};
			
	var bindEvent = function(el, data){
		$.each(el.attributes, function(){
			if(this.name && el.value != "" && this.name.substring(0, 9) == 'jb-event-') {
				var evtName = this.name.substring(9);
				var evtValue = this.value;
				if(evtName == 'save') {
					$(el).on('click', function() { evtSave(el, source); self.settings.events[evtValue](el, source); } );
				} else {
					$(el).on(evtName, function() { self.settings.events[evtValue](el, data); } );
				}
				$(el).removeAttr(this.name);
			}
		});
	};

	var bindRepeater = function(rebind){
		var dfd = $.Deferred();
        
    	// clear everything before (re)bind when its
		if(!self.settings.persistent && rebind) {
			cachedItems = {};
			$("*[jb-render='2']",$context).html('');
		}

        $("*[jb-repeat]",$context).each(function(){
			var repeater = $(this);
			var div = null;

			var found = null;
			var tagName = repeater.prop('tagName');
			if(tagName == 'TR')
				found = repeater.parent()
			else
				found = repeater.prev();

			if(found.attr('jb-render') === '2')
				div = found;
			else if(tagName == 'TR') {
				div = $('<tbody jb-render="2" />');
				repeater.parent().before(div);
			} else {
				div = $('<' + tagName + ' jb-render="2" />');
				repeater.before(div);
			}

			var prevCached = $.extend(true, {}, cachedItems);

			var childLen = div.children().length;

			var sameParent = repeater.closest('div[jb-context]');
			if(sameParent.attr('jb-context') !== contextName) return;
			
			var expr = repeater.attr('jb-repeat');
			var matches = expr.match(/\((\w+),\s?(\w+)\s?\) in (\w+)/);
			var keyPath = matches[1];
			var valuePath = matches[2];
			var sourcePath = matches[3];
						
			if(!source[sourcePath]) return;
		
			for(var i = 0; i < source[sourcePath].length; i++) {
				var obj = {};
				obj[keyPath] = i;
				obj[valuePath] = source[sourcePath][i];

				crc = checksum(JSON.stringify(obj));
				
				if(cachedItems.hasOwnProperty(crc))
					continue;

				var copy = repeater.clone();
				copy.removeAttr('jb-repeat');
				copy.css('display','');

				copy.attr('crc', crc);
				cachedItems[crc] = copy;

				parseBindAttr(obj, copy);
				bindControls( obj, copy, repeater);
						
				copy.find('div[jb-context]').each(function(){
					var ctxName = $(this).attr('jb-context');
					bindContext($(this), ctxName, obj[valuePath]);
				});

				// lifetime of the DOM if defined in settings
				if(self.settings.lifetime > 0)
					setTimeout(function(){ copy.remove() }, self.settings.lifetime);
				
				if(childLen >= i + 1) {
					var cur = div.children().eq(i);
					var crc = cur.attr('crc');
					if(cachedItems.hasOwnProperty(crc))
						delete cachedItems[crc];
					cur.replaceWith(copy);
				} else
					copy.appendTo(div);
			}

			if(source[sourcePath].length < childLen) {
				var toBeRemoved = div.children().slice(source[sourcePath].length);
				$.each(toBeRemoved, function(){
					var crc = $(this).attr('crc');
					if(cachedItems.hasOwnProperty(crc))
						delete cachedItems[crc];
					$(this).remove();
				});
			}
		});

		dfd.resolve();
		return dfd.promise();
	};
	
	// the "constructor" method that gets called when the object is created
	var __construct = function() {
		self.settings = $.extend({}, defaults, options);
		$context = $('div[jb-context="'+contextName+'"]');
		CustomBind.$collection[contextName] = self;
		crcTable = _makeCRCTable();
	}();
}

CustomBind.$collection = {};
$(function(){
	CustomBind.$ctxLoading = new CustomBind('ctxLoading', {allowHide: false, showLoading: false, noAsync: true, hideOther: false, persistent: true});
});
