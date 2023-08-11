
/*
 * Copyright (C) Igor Sysoev
 * Copyright (C) Nginx, Inc.
 */


#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>


#define ngx_http_upstream_tries(p) ((p)->tries                                \
                                    + ((p)->next ? (p)->next->tries : 0))


static ngx_http_upstream_rr_peer_t *ngx_http_upstream_get_peer(
    ngx_http_upstream_rr_peer_data_t *rrp);


#if (NGX_HTTP_SSL)

static ngx_int_t ngx_http_upstream_empty_set_session(ngx_peer_connection_t *pc,
    void *data);
static void ngx_http_upstream_empty_save_session(ngx_peer_connection_t *pc,
    void *data);

#endif

void 
custom_server_init(custom_versioned_server_t *version, ngx_int_t id)
{
    ngx_atomic_t * lock;
    
    version->id = id;
    
    version->completed_requests = 0;
    version->max_prediction = 0;
    version->req_upper_bound = INT_MAX - 5;
    version->active_req = 0;
    version->predicted_avg_rt = 0;
    version->predict = 0;
    version->latest = 0;
    version->avg_service_time = 0;
    version->req_times = (req_time_t **) malloc(sizeof(req_time_t *));
    version->req_tail = (req_time_t **) malloc(sizeof(req_time_t *));
    *(version->req_times) = NULL;
    *(version->req_tail) = NULL;
    
    version->service_time = 0;
    version->service_time_update_sec = 0;
    version->service_time_update_msec = 0;
    version->curr_load = 0;
       
    lock = malloc(sizeof(ngx_atomic_t));
    if (lock == NULL) {
    	return;
    }
    
    version->lock = lock;   
    return;
}

ngx_int_t
ngx_http_upstream_init_round_robin(ngx_conf_t *cf,
    ngx_http_upstream_srv_conf_t *us)
{
    ngx_url_t                      u;
    ngx_uint_t                     i, j, n, w, t, pt;
    ngx_http_upstream_server_t    *server;
    ngx_http_upstream_rr_peer_t   *peer, **peerp;
    ngx_http_upstream_rr_peers_t  *peers, *backup;
    //custom_versioned_server_t     *heavy, *light;
    custom_versioned_server_t     *version;

    us->peer.init = ngx_http_upstream_init_round_robin_peer;

    if (us->servers) {
        server = us->servers->elts;

        n = 0;
        w = 0;
        t = 0;
        pt = 0;

        for (i = 0; i < us->servers->nelts; i++) {
            if (server[i].backup) {
                continue;
            }

            n += server[i].naddrs;
            w += server[i].naddrs * server[i].weight;

            if (!server[i].down) {
                t += server[i].naddrs;
            }
            
            if (server[i].pt > 0) {
                pt = server[i].pt;
            }
        }

        if (n == 0) {
            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "no servers in upstream \"%V\" in %s:%ui",
                          &us->host, us->file_name, us->line);
            return NGX_ERROR;
        }

        peers = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peers_t));
        if (peers == NULL) {
            return NGX_ERROR;
        }

        peer = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peer_t) * n);
        if (peer == NULL) {
            return NGX_ERROR;
        }
        
        /*
	heavy = malloc(sizeof(custom_versioned_server_t));
	if (heavy == NULL) {
	    return NGX_ERROR;
	}
	
	light = malloc(sizeof(custom_versioned_server_t));
	if (light == NULL) {
	    return NGX_ERROR;
	}
	
	custom_server_init(heavy, 4);
	custom_server_init(light, 2);
	*/
	
        peers->single = (n == 1);
        peers->number = n;
        peers->weighted = (w != n);
        peers->total_weight = w;
        peers->tries = t;
        peers->name = &us->host;
        peers->log_time = -1;
        peers->max_req = 0;
        peers->active_req = 0;

        n = 0;
        peerp = &peers->peer;

        for (i = 0; i < us->servers->nelts; i++) {
            if (server[i].backup) {
                continue;
            }

            for (j = 0; j < server[i].naddrs; j++) {
                peer[n].sockaddr = server[i].addrs[j].sockaddr;
                peer[n].socklen = server[i].addrs[j].socklen;
                peer[n].name = server[i].addrs[j].name;
                peer[n].weight = server[i].weight;
                
                
                char * name_copy = malloc(sizeof(char) * 60);
                strcpy(name_copy, (char *) peer[n].name.data);
                
                char * name_ptr = strtok(name_copy, ":");
                
                version = malloc(sizeof(custom_versioned_server_t));
                if (server[i].weight == 2) {
                    custom_server_init(version, 4);
                    peer[n].heavy = version; 
                }
                else {
                    custom_server_init(version, 2);
                    peer[n].light = version;
                }
                peer[n].version = version;
                
                
                if (name_ptr != NULL) {
                    peer[n].version->ip = name_ptr;
                    name_ptr = strtok(NULL, "");
                }
                
                if (name_ptr != NULL) {
                    peer[n].version->port = atoi(name_ptr);
                }
                
                peer[n].effective_weight = server[i].weight;
                peer[n].current_weight = 0;
                peer[n].max_conns = server[i].max_conns;
                peer[n].max_fails = server[i].max_fails;
                peer[n].fail_timeout = server[i].fail_timeout;
                peer[n].down = server[i].down;
                peer[n].server = server[i].name;
                peer[n].pt = pt;

                *peerp = &peer[n];
                peerp = &peer[n].next;
                n++;
            }
        }

        us->peer.data = peers;

        /* backup servers */

        n = 0;
        w = 0;
        t = 0;

        for (i = 0; i < us->servers->nelts; i++) {
            if (!server[i].backup) {
                continue;
            }

            n += server[i].naddrs;
            w += server[i].naddrs * server[i].weight;

            if (!server[i].down) {
                t += server[i].naddrs;
            }
        }

        if (n == 0) {
            return NGX_OK;
        }

        backup = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peers_t));
        if (backup == NULL) {
            return NGX_ERROR;
        }

        peer = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peer_t) * n);
        if (peer == NULL) {
            return NGX_ERROR;
        }

        peers->single = 0;
        backup->single = 0;
        backup->number = n;
        backup->weighted = (w != n);
        backup->total_weight = w;
        backup->tries = t;
        backup->name = &us->host;

        n = 0;
        peerp = &backup->peer;

        for (i = 0; i < us->servers->nelts; i++) {
            if (!server[i].backup) {
                continue;
            }

            for (j = 0; j < server[i].naddrs; j++) {
                peer[n].sockaddr = server[i].addrs[j].sockaddr;
                peer[n].socklen = server[i].addrs[j].socklen;
                peer[n].name = server[i].addrs[j].name;
                peer[n].weight = server[i].weight;
                peer[n].effective_weight = server[i].weight;
                peer[n].current_weight = 0;
                peer[n].max_conns = server[i].max_conns;
                peer[n].max_fails = server[i].max_fails;
                peer[n].fail_timeout = server[i].fail_timeout;
                peer[n].down = server[i].down;
                peer[n].server = server[i].name;

                *peerp = &peer[n];
                peerp = &peer[n].next;
                n++;
            }
        }

        peers->next = backup;

        return NGX_OK;
    }


    /* an upstream implicitly defined by proxy_pass, etc. */

    if (us->port == 0) {
        ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                      "no port in upstream \"%V\" in %s:%ui",
                      &us->host, us->file_name, us->line);
        return NGX_ERROR;
    }

    ngx_memzero(&u, sizeof(ngx_url_t));

    u.host = us->host;
    u.port = us->port;

    if (ngx_inet_resolve_host(cf->pool, &u) != NGX_OK) {
        if (u.err) {
            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "%s in upstream \"%V\" in %s:%ui",
                          u.err, &us->host, us->file_name, us->line);
        }

        return NGX_ERROR;
    }

    n = u.naddrs;

    peers = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peers_t));
    if (peers == NULL) {
        return NGX_ERROR;
    }

    peer = ngx_pcalloc(cf->pool, sizeof(ngx_http_upstream_rr_peer_t) * n);
    if (peer == NULL) {
        return NGX_ERROR;
    }

    peers->single = (n == 1);
    peers->number = n;
    peers->weighted = 0;
    peers->total_weight = n;
    peers->tries = n;
    peers->name = &us->host;

    peerp = &peers->peer;

    for (i = 0; i < u.naddrs; i++) {
        peer[i].sockaddr = u.addrs[i].sockaddr;
        peer[i].socklen = u.addrs[i].socklen;
        peer[i].name = u.addrs[i].name;
        peer[i].weight = 1;
        peer[i].effective_weight = 1;
        peer[i].current_weight = 0;
        peer[i].max_conns = 0;
        peer[i].max_fails = 1;
        peer[i].fail_timeout = 10;
        *peerp = &peer[i];
        peerp = &peer[i].next;
    }

    us->peer.data = peers;

    /* implicitly defined upstream has no backup servers */

    return NGX_OK;
}


ngx_int_t
ngx_http_upstream_init_round_robin_peer(ngx_http_request_t *r,
    ngx_http_upstream_srv_conf_t *us)
{
    ngx_uint_t                         n;
    ngx_http_upstream_rr_peer_data_t  *rrp;

    rrp = r->upstream->peer.data;

    if (rrp == NULL) {
        rrp = ngx_palloc(r->pool, sizeof(ngx_http_upstream_rr_peer_data_t));
        if (rrp == NULL) {
            return NGX_ERROR;
        }

        r->upstream->peer.data = rrp;
    }
    
    rrp->peers = us->peer.data;
    rrp->current = NULL;
    rrp->config = 0;

    n = rrp->peers->number;

    if (rrp->peers->next && rrp->peers->next->number > n) {
        n = rrp->peers->next->number;
    }

    if (n <= 8 * sizeof(uintptr_t)) {
        rrp->tried = &rrp->data;
        rrp->data = 0;

    } else {
        n = (n + (8 * sizeof(uintptr_t) - 1)) / (8 * sizeof(uintptr_t));

        rrp->tried = ngx_pcalloc(r->pool, n * sizeof(uintptr_t));
        if (rrp->tried == NULL) {
            return NGX_ERROR;
        }
    }

    r->upstream->peer.get = ngx_http_upstream_get_round_robin_peer;
    r->upstream->peer.free = ngx_http_upstream_free_round_robin_peer;
    r->upstream->peer.tries = ngx_http_upstream_tries(rrp->peers);
#if (NGX_HTTP_SSL)
    r->upstream->peer.set_session =
                               ngx_http_upstream_set_round_robin_peer_session;
    r->upstream->peer.save_session =
                               ngx_http_upstream_save_round_robin_peer_session;
#endif

    return NGX_OK;
}


ngx_int_t
ngx_http_upstream_create_round_robin_peer(ngx_http_request_t *r,
    ngx_http_upstream_resolved_t *ur)
{
    u_char                            *p;
    size_t                             len;
    socklen_t                          socklen;
    ngx_uint_t                         i, n;
    struct sockaddr                   *sockaddr;
    ngx_http_upstream_rr_peer_t       *peer, **peerp;
    ngx_http_upstream_rr_peers_t      *peers;
    ngx_http_upstream_rr_peer_data_t  *rrp;

    rrp = r->upstream->peer.data;

    if (rrp == NULL) {
        rrp = ngx_palloc(r->pool, sizeof(ngx_http_upstream_rr_peer_data_t));
        if (rrp == NULL) {
            return NGX_ERROR;
        }

        r->upstream->peer.data = rrp;
    }

    peers = ngx_pcalloc(r->pool, sizeof(ngx_http_upstream_rr_peers_t));
    if (peers == NULL) {
        return NGX_ERROR;
    }

    peer = ngx_pcalloc(r->pool, sizeof(ngx_http_upstream_rr_peer_t)
                                * ur->naddrs);
    if (peer == NULL) {
        return NGX_ERROR;
    }

    peers->single = (ur->naddrs == 1);
    peers->number = ur->naddrs;
    peers->tries = ur->naddrs;
    peers->name = &ur->host;

    if (ur->sockaddr) {
        peer[0].sockaddr = ur->sockaddr;
        peer[0].socklen = ur->socklen;
        peer[0].name = ur->name.data ? ur->name : ur->host;
        peer[0].weight = 1;
        peer[0].effective_weight = 1;
        peer[0].current_weight = 0;
        peer[0].max_conns = 0;
        peer[0].max_fails = 1;
        peer[0].fail_timeout = 10;
        peers->peer = peer;

    } else {
        peerp = &peers->peer;

        for (i = 0; i < ur->naddrs; i++) {

            socklen = ur->addrs[i].socklen;

            sockaddr = ngx_palloc(r->pool, socklen);
            if (sockaddr == NULL) {
                return NGX_ERROR;
            }

            ngx_memcpy(sockaddr, ur->addrs[i].sockaddr, socklen);
            ngx_inet_set_port(sockaddr, ur->port);

            p = ngx_pnalloc(r->pool, NGX_SOCKADDR_STRLEN);
            if (p == NULL) {
                return NGX_ERROR;
            }

            len = ngx_sock_ntop(sockaddr, socklen, p, NGX_SOCKADDR_STRLEN, 1);

            peer[i].sockaddr = sockaddr;
            peer[i].socklen = socklen;
            peer[i].name.len = len;
            peer[i].name.data = p;
            peer[i].weight = 1;
            peer[i].effective_weight = 1;
            peer[i].current_weight = 0;
            peer[i].max_conns = 0;
            peer[i].max_fails = 1;
            peer[i].fail_timeout = 10;
            *peerp = &peer[i];
            peerp = &peer[i].next;
        }
    }

    rrp->peers = peers;
    rrp->current = NULL;
    rrp->config = 0;

    if (rrp->peers->number <= 8 * sizeof(uintptr_t)) {
        rrp->tried = &rrp->data;
        rrp->data = 0;

    } else {
        n = (rrp->peers->number + (8 * sizeof(uintptr_t) - 1))
                / (8 * sizeof(uintptr_t));

        rrp->tried = ngx_pcalloc(r->pool, n * sizeof(uintptr_t));
        if (rrp->tried == NULL) {
            return NGX_ERROR;
        }
    }

    r->upstream->peer.get = ngx_http_upstream_get_round_robin_peer;
    r->upstream->peer.free = ngx_http_upstream_free_round_robin_peer;
    r->upstream->peer.tries = ngx_http_upstream_tries(rrp->peers);
#if (NGX_HTTP_SSL)
    r->upstream->peer.set_session = ngx_http_upstream_empty_set_session;
    r->upstream->peer.save_session = ngx_http_upstream_empty_save_session;
#endif

    return NGX_OK;
}



void
ngx_http_upstream_buffer_request_data(ngx_peer_connection_t *pc) {
    ngx_http_upstream_rr_peer_data_t  *rrp = pc->data;
    //ngx_http_upstream_rr_peers_wlock(rrp->peers);
    
    /*
    custom_req_data_t ** buffer = pc->req_buffer;
    custom_req_data_t * curr_req;
    
    if (*buffer == NULL) {
        custom_req_data_t * buffer_element = malloc(sizeof(custom_req_data_t));
        *buffer = buffer_element;
        curr_req = buffer_element;
    }
    else {
    	custom_req_data_t * curr_el = *buffer;
    	while(curr_el->next != NULL) {
    	    curr_el = curr_el->next;
    	}
    	
    	custom_req_data_t * buffer_element = malloc(sizeof(custom_req_data_t));
        curr_el->next = buffer_element;
        curr_req = buffer_element;
    }
    
    custom_versioned_server_t * v = rrp->current->version;
    ngx_time_t *tp = ngx_timeofday();
    
    v->service_time += ((tp->sec - v->service_time_update_sec) * 1000 + (tp->msec - v->service_time_update_msec)) * (v->active_req-1); 
    v->service_time += ((tp->sec - start_s) * 1000 + (tp->msec - start_ms));
    v->service_time_update_sec = tp->sec;
    v->service_time_update_msec = tp->msec;
    
    curr_req->version = v;
    curr_req->req_num = count;
    curr_req->completed = v->completed_requests;
    curr_req->active = v->active_req;
    curr_req->latest_finished = v->latest;
    curr_req->predict = v->predict;
       
    req_time_t * new_req_time = (req_time_t *) malloc(sizeof(req_time_t));
    curr_req->req_obj = new_req_time;
    
    if (new_req_time == NULL) {
        return;
    }
    else {
        new_req_time->sec = start_s;
        new_req_time->msec = start_ms;
        new_req_time->next = NULL;
        new_req_time->tail = NULL;
        
        req_time_t ** time_list = v->req_times;
        req_time_t ** tail = v->req_tail;
        
        if (*time_list == NULL) {
            *time_list = new_req_time;
            *tail = new_req_time;
        }
        else {
            (*tail)->next = new_req_time;
            *tail = new_req_time;
        }
    }
    */
    
    ngx_http_request_t *r = (ngx_http_request_t *) pc->req_buffer;
    
    custom_versioned_server_t * v = rrp->current->version;
    ngx_time_t *tp = ngx_timeofday();
    
    v->service_time += ((tp->sec - v->service_time_update_sec) * 1000 + (tp->msec - v->service_time_update_msec)) * (v->active_req-1); 
    v->service_time += ((tp->sec - r->start_sec) * 1000 + (tp->msec - r->start_msec));
    v->service_time_update_sec = tp->sec;
    v->service_time_update_msec = tp->msec;
    
    r->version = v;
    r->req_finish_before =  v->completed_requests;
    r->no = r->req_finish_before + v->active_req;
    r->last_complete = v->latest;
    r->predict = v->predict;
       
    req_time_t * new_req_time = (req_time_t *) malloc(sizeof(req_time_t));
    
    if (new_req_time != NULL) {
        new_req_time->sec = r->start_sec;
        new_req_time->msec = r->start_msec;
        new_req_time->next = NULL;
        new_req_time->tail = NULL;
        
        req_time_t ** time_list = v->req_times;
        req_time_t ** tail = v->req_tail;
        
        if (*time_list == NULL) {
            *time_list = new_req_time;
            *tail = new_req_time;
        }
        else {
            (*tail)->next = new_req_time;
            *tail = new_req_time;
        }
    }
    
    r->enter_time = new_req_time;
    
    //ngx_http_upstream_rr_peers_unlock(rrp->peers);
}



ngx_int_t
ngx_http_upstream_get_round_robin_peer(ngx_peer_connection_t *pc, void *data)
{
    ngx_http_upstream_rr_peer_data_t  *rrp = data;

    ngx_int_t                      rc;
    ngx_uint_t                     i, n;
    ngx_http_upstream_rr_peer_t   *peer;
    ngx_http_upstream_rr_peers_t  *peers;

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "get rr peer, try: %ui", pc->tries);

    pc->cached = 0;
    pc->connection = NULL;

    peers = rrp->peers;
    ngx_http_upstream_rr_peers_wlock(peers);

    peer = ngx_http_upstream_get_peer(rrp);

    if (peer == NULL) {
        goto failed;
    }        

    if (peer->light != NULL) {
          ngx_log_debug2(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "version light: %p %ims",
                   peer, peer->light->predicted_avg_rt);
         
    }
    if (peer->heavy != NULL) {
          ngx_log_debug2(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "version heavy: %p %ims",
                   peer, peer->heavy->predicted_avg_rt);
    }	
    
    ngx_log_debug2(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "get rr peer, current: %p %i",
                   peer, peer->current_weight);
    
    pc->sockaddr = peer->sockaddr;
    pc->socklen = peer->socklen;
    pc->name = &peer->name;

    peer->conns++;
    
    ngx_http_upstream_buffer_request_data(pc);

    ngx_http_upstream_rr_peers_unlock(peers);

    return NGX_OK;

failed:

    if (peers->next) {

        ngx_log_debug0(NGX_LOG_DEBUG_HTTP, pc->log, 0, "backup servers");

        rrp->peers = peers->next;

        n = (rrp->peers->number + (8 * sizeof(uintptr_t) - 1))
                / (8 * sizeof(uintptr_t));

        for (i = 0; i < n; i++) {
            rrp->tried[i] = 0;
        }

        ngx_http_upstream_rr_peers_unlock(peers);

        rc = ngx_http_upstream_get_round_robin_peer(pc, rrp);

        if (rc != NGX_BUSY) {
            return rc;
        }

        ngx_http_upstream_rr_peers_wlock(peers);
    }

    ngx_http_upstream_rr_peers_unlock(peers);

    pc->name = peers->name;

    return NGX_BUSY;
}


static ngx_http_upstream_rr_peer_t *
ngx_http_upstream_get_peer(ngx_http_upstream_rr_peer_data_t *rrp)
{
    time_t                        now;
    uintptr_t                     m;
    ngx_int_t                     pt, heavy_oldest;
    float                         heavy_load, light_load;
    ngx_uint_t                    i, n;
    ngx_http_upstream_rr_peer_t  *peer, *best, *heavy, *light;

    now = ngx_time();

    best = NULL;

#if (NGX_SUPPRESS_WARN)
    //p = 0;
#endif
    
    heavy = NULL;
    light = NULL;
    pt = 0;
    heavy_oldest = 0;
    heavy_load = 0.0f; light_load = 0.0f;
    
    ngx_time_t * tp = ngx_timeofday();
    
    
    for (peer = rrp->peers->peer, i = 0;
         peer;
         peer = peer->next, i++) {
         
        if (peer->pt > 0) {
            pt = peer->pt;
        }
    }
    
    
    
    for (peer = rrp->peers->peer, i = 0;
         peer;
         peer = peer->next, i++)
    {
        n = i / (8 * sizeof(uintptr_t));
        m = (uintptr_t) 1 << i % (8 * sizeof(uintptr_t));

        if (rrp->tried[n] & m) {
            continue;
        }

        if (peer->down) {
            continue;
        }

        if (peer->max_fails
            && peer->fails >= peer->max_fails
            && now - peer->checked <= peer->fail_timeout)
        {
            continue;
        }

        if (peer->max_conns && peer->conns >= peer->max_conns) {
            continue;
        }
        
        /*
        if (peer->heavy != NULL) {
            heavy = peer;
        }
        else if (peer->light != NULL) {
            light = peer;
        }*/
             
        req_time_t ** time_list = peer->version->req_times;
	while ((*time_list) != NULL && (*time_list)->sec == -1) {
	    req_time_t * next = (*time_list)->next;
	    free(*time_list);
            *time_list = next;
        }
        
        
        if (peer->version->max_prediction >= pt) {
            peer->version->predicted_avg_rt = pt - 1;
            peer->version->max_prediction = pt - 1;
        }
        
        ngx_int_t oldest = 0;
        if (*time_list != NULL && (*time_list)->sec != -1) {
            oldest = (tp->sec - (*time_list)->sec) * 1000 + (tp->msec - (*time_list)->msec);
        }
        
        //ngx_int_t elapsed = (tp->sec - heavy->version->service_time_update_sec) * 1000 + (tp->msec - heavy->version->service_time_update_msec);
        float load = (peer->version->predicted_avg_rt * (peer->version->active_req + 1));
        //float avg_service = heavy->version->avg_service_time * heavy->version->active_req;
        //load += ngx_max(0, (avg_service - (elapsed * heavy->version->active_req + heavy->version->service_time)) / ngx_max(1, avg_service));
        
        if (peer->version->completed_requests + peer->version->active_req < 200) {
            peer->version->predicted_avg_rt = peer->version->predicted_avg_rt * 0.99;
        }
        
        if (heavy == NULL && peer->heavy != NULL) {
            heavy = peer;
            heavy_load = load;
            heavy_oldest = oldest;            
            continue;
        }
        else if (light == NULL && peer->light != NULL) {
            light = peer;
            light_load = load;
            continue;
        }
           
        
        //if (peer->heavy != NULL && (load < heavy_load) && (oldest + peer->version->predicted_avg_rt < pt)) {
        if (peer->heavy != NULL && (load < heavy_load)) {
            heavy = peer;
            heavy_load = load;
            heavy_oldest = oldest;
        }
        //else if (peer->light != NULL && (load < light_load) && (oldest + peer->version->predicted_avg_rt < pt)) {
        else if (peer->light != NULL && (load < light_load)) {
            light = peer;
            light_load = load;
        }
        
    }
    
    /*
    req_time_t ** time_list = heavy->version->req_times;
    while ((*time_list) != NULL && (*time_list)->sec == -1) {
        req_time_t * next = (*time_list)->next;
        free(*time_list);
        *time_list = next;
    }
    
    if (pt == 0) {
        return heavy;
    }
    
    if (heavy->version->predicted_avg_rt >= pt) {
        heavy->version->predicted_avg_rt = pt - 1;
    }
    
    ngx_time_t * tp = ngx_timeofday();
    ngx_int_t oldest = 0;
    if (*time_list != NULL && (*time_list)->sec != -1) {
        oldest = (tp->sec - (*time_list)->sec) * 1000 + (tp->msec - (*time_list)->msec);
    }
        
    ngx_int_t elapsed = (tp->sec - heavy->version->service_time_update_sec) * 1000 + (tp->msec - heavy->version->service_time_update_msec);
    
    float load = (heavy->version->predicted_avg_rt * (heavy->version->active_req + 1));	
    float avg_service = heavy->version->avg_service_time * heavy->version->active_req;
    load += ngx_max(0, (avg_service - (elapsed * heavy->version->active_req + heavy->version->service_time)) / ngx_max(1, avg_service));
    */
    
    if (heavy == NULL) {
        best = light;
    }
    else if (light == NULL) {
        best = heavy;
    }
    else {
    
        if (heavy_oldest > 0 && (heavy_oldest + heavy->version->predicted_avg_rt) >= pt) {
        	best = light;
        }
        else if (heavy_load >= pt) {
            best = light;
        }
        else {
            best = heavy;
        }
    }
    
    
    ngx_int_t elapsed = (tp->sec - best->version->service_time_update_sec) * 1000 + (tp->msec - best->version->service_time_update_msec);
    best->version->service_time = elapsed * best->version->active_req + best->version->service_time;
    if (best->version->avg_service_time == 0) {
        best->version->avg_service_time =  ((float) best->version->service_time) / ngx_max(1, best->version->active_req);
    }
    else {
        best->version->avg_service_time = (0.95 * best->version->avg_service_time) + 0.05 * (((float) best->version->service_time) / ngx_max(1, best->version->active_req)); 
    }
    
    best->version->service_time_update_sec = tp->sec;
    best->version->service_time_update_msec = tp->msec;
    best->version->curr_load = best == heavy ? heavy_load : light_load;
    
    best->version->predict = best == heavy ? heavy_load : light_load;
    if (best == NULL) {
        return NULL;
    }
    
    best->checked = now;
   
    best->version->active_req += 1;
    rrp->peers->active_req += 1;
    rrp->peers->max_req = ngx_max(rrp->peers->active_req, rrp->peers->max_req);
    rrp->current = best;
    return best;
}


void
ngx_http_upstream_free_round_robin_peer(ngx_peer_connection_t *pc, void *data,
    ngx_uint_t state)
{
    ngx_http_upstream_rr_peer_data_t  *rrp = data;

    time_t                       now;
    ngx_http_upstream_rr_peer_t  *peer;

    ngx_log_debug2(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "free rr peer %ui %ui", pc->tries, state);

    /* TODO: NGX_PEER_KEEPALIVE */

    peer = rrp->current;

    ngx_http_upstream_rr_peers_rlock(rrp->peers);
    ngx_http_upstream_rr_peer_lock(rrp->peers, peer);

    if (rrp->peers->single) {

        peer->conns--;

        ngx_http_upstream_rr_peer_unlock(rrp->peers, peer);
        ngx_http_upstream_rr_peers_unlock(rrp->peers);

        pc->tries = 0;
        return;
    }

    if (state & NGX_PEER_FAILED) {
        now = ngx_time();

        peer->fails++;
        peer->accessed = now;
        peer->checked = now;

        if (peer->max_fails) {
            peer->effective_weight -= peer->weight / peer->max_fails;

            if (peer->fails >= peer->max_fails) {
                ngx_log_error(NGX_LOG_WARN, pc->log, 0,
                              "upstream server temporarily disabled");
            }
        }

        ngx_log_debug2(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                       "free rr peer failed: %p %i",
                       peer, peer->effective_weight);

        if (peer->effective_weight < 0) {
            peer->effective_weight = 0;
        }

    } else {

        /* mark peer live if check passed */

        if (peer->accessed < peer->checked) {
            peer->fails = 0;
        }
    }

    peer->conns--;

    ngx_http_upstream_rr_peer_unlock(rrp->peers, peer);
    ngx_http_upstream_rr_peers_unlock(rrp->peers);

    if (pc->tries) {
        pc->tries--;
    }
}


#if (NGX_HTTP_SSL)

ngx_int_t
ngx_http_upstream_set_round_robin_peer_session(ngx_peer_connection_t *pc,
    void *data)
{
    ngx_http_upstream_rr_peer_data_t  *rrp = data;

    ngx_int_t                      rc;
    ngx_ssl_session_t             *ssl_session;
    ngx_http_upstream_rr_peer_t   *peer;
#if (NGX_HTTP_UPSTREAM_ZONE)
    int                            len;
    const u_char                  *p;
    ngx_http_upstream_rr_peers_t  *peers;
    u_char                         buf[NGX_SSL_MAX_SESSION_SIZE];
#endif

    peer = rrp->current;

#if (NGX_HTTP_UPSTREAM_ZONE)
    peers = rrp->peers;

    if (peers->shpool) {
        ngx_http_upstream_rr_peers_rlock(peers);
        ngx_http_upstream_rr_peer_lock(peers, peer);

        if (peer->ssl_session == NULL) {
            ngx_http_upstream_rr_peer_unlock(peers, peer);
            ngx_http_upstream_rr_peers_unlock(peers);
            return NGX_OK;
        }

        len = peer->ssl_session_len;

        ngx_memcpy(buf, peer->ssl_session, len);

        ngx_http_upstream_rr_peer_unlock(peers, peer);
        ngx_http_upstream_rr_peers_unlock(peers);

        p = buf;
        ssl_session = d2i_SSL_SESSION(NULL, &p, len);

        rc = ngx_ssl_set_session(pc->connection, ssl_session);

        ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                       "set session: %p", ssl_session);

        ngx_ssl_free_session(ssl_session);

        return rc;
    }
#endif

    ssl_session = peer->ssl_session;

    rc = ngx_ssl_set_session(pc->connection, ssl_session);

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "set session: %p", ssl_session);

    return rc;
}


void
ngx_http_upstream_save_round_robin_peer_session(ngx_peer_connection_t *pc,
    void *data)
{
    ngx_http_upstream_rr_peer_data_t  *rrp = data;

    ngx_ssl_session_t             *old_ssl_session, *ssl_session;
    ngx_http_upstream_rr_peer_t   *peer;
#if (NGX_HTTP_UPSTREAM_ZONE)
    int                            len;
    u_char                        *p;
    ngx_http_upstream_rr_peers_t  *peers;
    u_char                         buf[NGX_SSL_MAX_SESSION_SIZE];
#endif

#if (NGX_HTTP_UPSTREAM_ZONE)
    peers = rrp->peers;

    if (peers->shpool) {

        ssl_session = ngx_ssl_get0_session(pc->connection);

        if (ssl_session == NULL) {
            return;
        }

        ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                       "save session: %p", ssl_session);

        len = i2d_SSL_SESSION(ssl_session, NULL);

        /* do not cache too big session */

        if (len > NGX_SSL_MAX_SESSION_SIZE) {
            return;
        }

        p = buf;
        (void) i2d_SSL_SESSION(ssl_session, &p);

        peer = rrp->current;

        ngx_http_upstream_rr_peers_rlock(peers);
        ngx_http_upstream_rr_peer_lock(peers, peer);

        if (len > peer->ssl_session_len) {
            ngx_shmtx_lock(&peers->shpool->mutex);

            if (peer->ssl_session) {
                ngx_slab_free_locked(peers->shpool, peer->ssl_session);
            }

            peer->ssl_session = ngx_slab_alloc_locked(peers->shpool, len);

            ngx_shmtx_unlock(&peers->shpool->mutex);

            if (peer->ssl_session == NULL) {
                peer->ssl_session_len = 0;

                ngx_http_upstream_rr_peer_unlock(peers, peer);
                ngx_http_upstream_rr_peers_unlock(peers);
                return;
            }

            peer->ssl_session_len = len;
        }

        ngx_memcpy(peer->ssl_session, buf, len);

        ngx_http_upstream_rr_peer_unlock(peers, peer);
        ngx_http_upstream_rr_peers_unlock(peers);

        return;
    }
#endif

    ssl_session = ngx_ssl_get_session(pc->connection);

    if (ssl_session == NULL) {
        return;
    }

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                   "save session: %p", ssl_session);

    peer = rrp->current;

    old_ssl_session = peer->ssl_session;
    peer->ssl_session = ssl_session;

    if (old_ssl_session) {

        ngx_log_debug1(NGX_LOG_DEBUG_HTTP, pc->log, 0,
                       "old session: %p", old_ssl_session);

        /* TODO: may block */

        ngx_ssl_free_session(old_ssl_session);
    }
}


static ngx_int_t
ngx_http_upstream_empty_set_session(ngx_peer_connection_t *pc, void *data)
{
    return NGX_OK;
}


static void
ngx_http_upstream_empty_save_session(ngx_peer_connection_t *pc, void *data)
{
    return;
}

#endif
