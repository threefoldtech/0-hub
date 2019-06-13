function repositories(source) {
    $("#trusted tbody").empty()
    $("#contributors tbody").empty();

    for(var index in source) {
        var repository = source[index];
        var username = repository['name'];

        var target = repository['official'] ? 'trusted' : 'contributors';
        var trclass = repository['official'] ? 'warning' : '';

        var span = $('<span>', {'class': 'glyphicon glyphicon-certificate ' + target});
        var href = $('<a>', {'href': username}).html(username);
        var tr = $('<tr>', {'class': trclass}).append($('<td>').append(span).append(href));

        $('#' + target + ' tbody').append(tr);
    }

    $(window).scrollTop(sessionStorage.getItem('scrollTop') || 0);
}

function flists(files, username) {
    $("#files tbody").empty();

    for(var index in files) {
        var file = files[index];

        var fileicon = $('<span>', {'class': 'glyphicon glyphicon-file'});
        var seeicon = $('<span>', {'class': 'glyphicon glyphicon-eye-open'});

        var filelink = $('<a>', {'href': '/' + username + '/' + file['name']}).html(file['name']);
        var seelink = $('<a>', {'href': '/' + username + '/' + file['name'] + '.md'}).append(seeicon);

        var filetd = $('<td>').append(fileicon).append(filelink);
        if(file['type'] == 'symlink')
            filetd.append($('<span>').html(" ➔ " + file['target']));

        var tr = $('<tr>');
        tr.append(filetd);
        tr.append($('<td>').append(seelink));
        tr.append($('<td>').html(file['size']));
        tr.append($('<td>').html(new Date(file['updated'] * 1000)));

        $('#files tbody').append(tr);
    }
}

function uswitch(username) {
    Cookies.set('active-user', username);
    $(".current-user").html(username);
    $("a.current-user").attr('href', '/' + username);
}
