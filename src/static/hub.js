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
        if(file['type'] == 'symlink') {
            var localusername = username;

            // cross repository symlink
            if(file['target'].includes("/"))
                localusername = '..';

            var link = localusername + '/' + file['target'] + '.md';

            filetd.append($('<span>').html(" ➔ "));
            filetd.append($('<a>', {'href': link}).html(file['target']));
        }

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

function fileslist(source) {
    $("#entries tbody").empty();
    $(".loading").hide();

    for(var index in source) {
        var repository = source[index];

        for(var entry in repository) {
            var item = repository[entry];

            var username = $('<td>').append($('<a>', {'href': index}).html(index));

            var filepath = index + "/" + item['name'] + '.md';
            var filename = $('<td>').append($('<a>', {'href': filepath}).html(item['name']));
            var size = $('<td>').html(item['size']);

            var tr = $('<tr>')
                .append(username)
                .append(filename)
                .append(size);

            $('#entries tbody').append(tr);
        }
    }
}

function clipboard(field) {
    var input = document.body.appendChild(document.createElement("input"));
    input.value = $(field).val();
    input.focus();
    input.select();

    document.execCommand('copy');
    input.parentNode.removeChild(input);
}
