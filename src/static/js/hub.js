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

function flists_file(file, username, tagname) {
    var output = {
        'size': file['size'],
        'updated': file['updated'],
    };

    var fileicon = $('<span>', {'class': 'glyphicon glyphicon-file'});
    var seeicon = $('<span>', {'class': 'glyphicon glyphicon-eye-open'});

    if(tagname) {
        var filelink = $('<a>', {'href': '/' + username + '/tags/' + tagname + '/' + file['name']}).html(file['name']);
        output['seelink'] = $('<a>', {'href': '/' + file['target'] + '.md'}).append(seeicon);

    } else {
        if(file['type'] == 'taglink') {
            var filelink = $('<span>').html(file['name']);
            output['seelink'] = $('<a>', {'href': file['target']}).append(seeicon);

        } else {
            var filelink = $('<a>', {'href': '/' + username + '/' + file['name']}).html(file['name']);
            output['seelink'] = $('<a>', {'href': '/' + username + '/' + file['name'] + '.md'}).append(seeicon);
        }
    }

    output['filetd'] = $('<td>').append(fileicon).append(filelink);

    if(file['type'] == 'symlink' || file['type'] == 'taglink') {
        var localusername = username + '/';

        // cross repository symlink
        if(file['target'].includes('/'))
            localusername = '/';

        var link = localusername + file['target'];
        if(!file['target'].includes('/tags/'))
            link += '.md';

        output['filetd'].append($('<span>').html(" ➔ "));
        output['filetd'].append($('<a>', {'href': link}).html(file['target']));
    }

    return output
}

function flists_tag(file, username) {
    var output = {
        'updated': file['updated'],
    };

    var fileicon = $('<span>', {'class': 'glyphicon glyphicon-tag'});
    var filelink = $('<a>', {'href': '/' + username + '/tags/' + file['name']}).html(file['name']);

    output['filetd'] = $('<td>').append(fileicon).append(filelink);

    return output;
}

function flists(files, username, tagname) {
    $("#files tbody").empty();
    $("#tags tbody").empty();

    if(files.length == 0) {
        $("#files tbody").append($('<tr>').append($('<td>', {'colspan': 4}).html("Nothing to show")));
    }

    for(var index in files) {
        let file = files[index];

        if(file['type'] == "regular" || file['type'] == "symlink" || file['type'] == "taglink") {
            let entry = flists_file(file, username, tagname);

            var tr = $('<tr>');
            tr.append(entry['filetd']);
            tr.append($('<td>').append(entry['seelink']));
            tr.append($('<td>').html(entry['size']));
            tr.append($('<td>').html(new Date(entry['updated'] * 1000)));

            $('#files tbody').append(tr);

        }

        if(file['type'] == "tag") {
            $("#tags").show();

            let entry = flists_tag(file, username);

            var tr = $('<tr>', {'class': 'warning'});
            tr.append(entry['filetd']);
            tr.append($('<td>').html(new Date(entry['updated'] * 1000)));

            $('#tags tbody').append(tr);
        }
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
