'use strict';

// Main application class

var Router = require('router');
var mediator = require('mediator');
var util = require('lib/util.js');

var ControlView = require('views/control-view');
var MapView = require('views/map-view');
var TileListView = require('views/tile-list-view');
var TileDetailView = require('views/tile-detail-view');


var App = function App () {
    var self = this;
    
    // emulate a view's anchorpoint
    self.el = null;
    self.$el = null;
    
    // contains all views that can display Results
    self.contentViews = [];
    self.controlView = null;
    self.tileListView = null;
    self.mapView = null;

    self.router = null;
    self.mediator = null;
    
    // should have them all here
    self.defaultSettings = {
        // we can't actually define them here, as these get set in controlView.defaults!
    	// see controlView.defaults for all their default values
		/*
		 * filterGroup: <int> if given, filters all content by the given group id
		 * availableFilters: <dict> the shown result filters by type
		 * activeFilters: <dict> the active (selected) current result filters by type
		 * basePageUrl: <str> the eg "/map/" url fragment as base of this page, used to build history URLs 
		 * 		(independent of search endpoint URLs)
		 */
    };
    
    self.defaultDisplayOptions = {
        showMap: true,
        showTiles: true,
        showControls: true,
        fullscreen: true,
        routeNavigation: true
    };
    self.displayOptions = {}
    self.defaultEl = '#app-fullscreen';
    self.defaultBasePageUrl = '/map/';
    
    self.passedOptions = null;
    
    
    /** Main entry point */
    self.start = function () {
        self.mediator = Backbone.mediator = mediator;
        self.mediator.settings = window.settings || {};
        
        var triggerResizeEvent = function (){
            Backbone.mediator.publish('resize:window');
        }
        var resizeTimer;
        // A global resize event with a delay so it won't fire constantly
        $(window).on('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(triggerResizeEvent, 500);
        });
        
        // init-module calls. inside a listener to the 'init:client' event,
        // one of these need to be called from the template to initialize the required modules
        Backbone.mediator.subscribe('init:module-full-routed', self.initModuleFullRouted, self);
        Backbone.mediator.subscribe('init:module-embed', self.initAppFromOptions, self);
        
        // - the 'init:client' signal is the marker for all pages using this client.js to now
        //      publish the "init:<module>" event for whichever module configuration they wish to load (see above)
        util.log('app.js: finish start() and publishing "init:client"')
        Backbone.mediator.publish('init:client');
        // we trigger both on the mediator and on html, in case scripts loaded earlier than this have already subsribed on 'html'
        $('html').trigger('init:client');
        
        return self;
    };
    
    /** Module configuration for a fullscreen App with full control of the page, that uses routing and history.
     *  This module uses the full set of default options and gets passed no options */
    self.initModuleFullRouted = function (options) {
    	self.passedOptions = options;
    	
    	self.router = new Router();
    	
        // (The first routing will autoinitialize views and model in self.navigate_map())
        Backbone.mediator.subscribe('navigate:map', self.navigate_map, self);
        Backbone.mediator.subscribe('navigate:router', self.router.on_navigate, self);
        
        // Start routing... this will automatically call `self.navigate_map()` once
        util.log('app.js: init routing')
        var root = options.basePageUrl || self.defaultBasePageUrl;
        Backbone.history.start({
            pushState: true,
            root: root
        });
    };
    
    /** Called on navigate, from router.js */
    self.navigate_map = function (event) {
    	// this will be called the on the first navigate to the URL, so we use
    	// it to init the app
        if (self.controlView == null) {
            self.initAppFromOptions(self.passedOptions);
        } else {
            Backbone.mediator.publish('app:stale-results', {reason: 'map-navigate'});
        }
    };
    

    /** Inits the app with many or no passed options.
     *  Default settings will be used for any options not passed.
     * 
     *  Many options can be configured for hiding the tile-list, disabling the visual control-view
     *  or enabling only specific Result model types. */
    self.initAppFromOptions = function (options) {
        // add passed options into params extended over the default options
    	var el = options.el ? options.el : self.defaultEl;
        var displayOptions = $.extend(true, {}, self.defaultDisplayOptions, options.display || {});
        var settings = $.extend(true, {}, self.defaultSettings, options.settings || {});
        var basePageUrl = options.basePageUrl || self.defaultBasePageUrl;
        
        self.init_app(el, basePageUrl, settings, displayOptions);
    };
    
    /** Main initialization function, this eventually gets called no matter which modules we load. */
    self.init_app = function (el, basePageUrl, settings, displayOptions) {
        util.log('app.js: init_app called with event, params')
        
        self.el = el;
        self.$el = $(self.el);
        
        self.displayOptions = displayOptions;
        
        var topicsJson = typeof COSINNUS_MAP_TOPICS_JSON !== 'undefined' ? COSINNUS_MAP_TOPICS_JSON : {};
        var portalInfo = typeof COSINNUS_PORTAL_INFOS !== 'undefined' ? COSINNUS_PORTAL_INFOS : {};
        
        var fullscreen = self.displayOptions.fullscreen;
        var splitscreen = self.displayOptions.showMap && self.displayOptions.showTiles;
        
        self.controlView = new ControlView({
                el: null, // will only be set if attached to tile-view
                availableFilters: settings.availableFilters,
                activeFilters: settings.activeFilters,
                allTopics: topicsJson,
                portalInfo: portalInfo,
                controlsEnabled: self.displayOptions.showControls,
                scrollControlsEnabled: self.displayOptions.showControls && self.displayOptions.showMap,
                paginationControlsEnabled: self.displayOptions.showTiles,
                filterGroup: settings.filterGroup,
                basePageURL: basePageUrl,
                showMine: settings.showMine,
                fullscreen: fullscreen,
                splitscreen: splitscreen
            }, 
            self, 
            null
        ); // collection=null here, gets instantiated in the control view
        self.contentViews.push(self.controlView);
        
        util.log('app.js: TODO: really do this if check for controlsEnabled?')
        util.log(self.displayOptions)
        
        
        if (self.displayOptions.showMap) {
            var mapView = new MapView({
                elParent: self.el,
                location: settings.location,
                fullscreen: fullscreen,
                splitscreen: splitscreen
            }, 
            self,
            self.controlView.collection
            ).render();
            self.mapView = mapView;
            self.contentViews.push(mapView);
        }
        
        if (self.displayOptions.showTiles) {
            var tileListView = new TileListView({
                elParent: self.el,
                fullscreen: fullscreen,
                splitscreen: splitscreen
            }, 
            self,
            self.controlView.collection
            ).render();
            self.contentViews.push(tileListView);
            self.tileListView = tileListView;
            
            // render control-view controls inside tile-list-view
            if (self.displayOptions.showControls) {
                util.log('app.js: actually rendering controls')
                self.controlView.setElement(tileListView.$el.find('.controls'));
                self.controlView.render();
            }
        }
        
        var tileDetailView = new TileDetailView({
            model: null,
            elParent: self.el,
            fullscreen: fullscreen,
            splitscreen: self.displayOptions.showMap && self.displayOptions.showTiles
        }, 
        self
        ).render();
        
        Backbone.mediator.publish('app:ready');
    };
};

module.exports = App;

$(function () {
    window.App = new App().start();
});
