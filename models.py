import sys
import logging
from google.appengine.ext import db

class Repository:

    def find_party_by_abbreviation(self, abbr):
        return db.Query(Party).filter('abbreviation =', abbr).get()

    def find_institute_by_name(self, name):
        return db.Query(Institute).filter('name = ', name).get()

    def find_recent_polls(self, count):
        return db.Query(Poll).order('publish_date').fetch(count)

    def remove_all_polling_data(self):
        for result in PollingResult.all():
            result.delete()
        for poll in Poll.all():
            poll.delete()

class Party(db.Model):
    name = db.StringProperty(required=True)
    abbreviation = db.StringProperty(required=True)
    color = db.StringProperty(required=True)

    def find_by_abbreviation(self, abbr):
        return db.GqlQuery("")

class Institute(db.Model):
    name = db.StringProperty(required=True)


class PollingResult(db.Model):
    party = db.ReferenceProperty(Party, required=True)
    percentage = db.FloatProperty(required=True)

    #def my_validate(self, errors):
    #    if self.percentage > 100.0:
    #        errors.add('Percentage must be smaller than or equal to 100.0: ' + self.percentage)
    #    if self.percentage < 0.0:
    #        errors.add('Percentage must be large than or equal to 0.0: ' + self.percentage)
    #    if self.party == None:
    #        errors.add('Party is required')
    #    return errors


class Poll(db.Model):
    publish_date = db.DateTimeProperty(required=True)
    institute = db.ReferenceProperty(Institute, required=True)
    results = db.ListProperty(db.Key, required=True)

    #def my_validate(self, errors):
    #    sum = 0.0
    #    for result in self.results:
    #        sum += result.percentage
    #    if sum != 100.0:
    #        errors.add('Sum of percentages must be 100.0: ' + sum)
    #    return errors

    def percentage_of(self, party):
        results = db.get(self.results)
        for result in results:
            if result.party.key() == party.key():
                return result.percentage
        return 0.0

        
class PollingAverage:
    left_parties = ['S','V','MP']
    right_parties = ['C','FP','M','KD']

    def __init__(self, polls):
        self.percentages = {}
        for poll in polls:
            for resultkey in poll.results:
                result = db.get(resultkey)
                if result.party.key() in self.percentages:
                    prev = self.percentages[result.party.key()]
                else:
                    prev = 0.0  

                self.percentages[result.party.key()] = prev + result.percentage
        for k, v in self.percentages.iteritems():
            self.percentages[k] = v/len(polls)

    def percentage_of(self, party):
        if party.key() in self.percentages:
            return self.percentages[party.key()]
        else:
            return 0.0

    def max_percentage(self):
        max = 0.0
        for k, v in self.percentages.iteritems():
            if v > max:
                max = v
        return max

    def left_block_percentage(self):    
        sum = 0
        for k, v in self.percentages.iteritems():
            party = db.get(k)
            if party.abbreviation in self.left_parties:
                sum += v
        return sum

    def right_block_percentage(self):
        sum = 0
        for k, v in self.percentages.iteritems():
            party = db.get(k)
            if party.abbreviation in self.right_parties:
                sum += v
        return sum

    def other_block_percentage(self):
        sum = 0
        for k, v in self.percentages.iteritems():
            party = db.get(k)
            if not (party.abbreviation in self.left_parties) and not (party.abbreviation in self.right_parties):
                sum += v
        return sum                

    def parties(self):
        return db.get(self.percentages.keys())
        
class Chart:
    chart_api_url = 'http://chart.apis.google.com/chart?'
    param_type = 'cht='
    param_dimension = 'chs='
    param_data = 'chd=t:'
    param_marker = 'chm='
    param_axes = 'chxt='
    param_ranges = 'chxr='
    param_colors = 'chco='
    param_labels = 'chl='
    param_scaling = 'chds='
    param_legends = 'chdl='

    def __init__(self, dimension, type):
        self.dimension = dimension
        self.type = type

    def add(self, param, value):
        return param + value

    def base_url(self):
        return self.chart_api_url + \
               self.add(self.param_type, self.type) + '&' + \
               self.add(self.param_dimension, self.dimension) + '&'


class PartyAverageBarChart(Chart):
    margin = 10
    param_bar_width = 'chbh='
    bar_width = 'a' # Automatic
    bar_spacing = '20'
    marker_color = 'dddddd'

    def __init__(self, avg):
        Chart.__init__(self, '600x400', 'bvs')
        self.avg = avg

    def build_url(self):
        ceil = 40.0
        cutoff_ratio = 4.0/ceil 
        url = Chart.base_url(self) + '&' + \
              Chart.add(self, 'chtt=', 'Partier') + '&' + \
              Chart.add(self, Chart.param_marker, 'r,' + self.marker_color + ',0,0,' + str(cutoff_ratio)) + '&' + \
              Chart.add(self, self.param_bar_width, self.bar_width + ',' + self.bar_spacing) + '&' + \
              Chart.add(self, Chart.param_scaling, '0,' + str(ceil)) + '&'

        data = colors = labels = ''
        for party in Party.all():
            data += str(self.avg.percentage_of(party)) + ','
            labels += party.abbreviation + ' ' + ('%.1f' % self.avg.percentage_of(party)) + ' %|'
            colors += party.color + '|'

        return url + Chart.add(self, Chart.param_data, data[0:-1]) + '&' + \
                     Chart.add(self, Chart.param_colors, colors[0:-1]) + '&' + \
                     Chart.add(self, Chart.param_axes, 'x,y') + '&' + \
                     Chart.add(self, Chart.param_ranges, '0,0,0|1,0,' + str(ceil)) + '&' + \
                     Chart.add(self, Chart.param_labels, labels[0:-1])


class PartyResultLineChart(Chart):
    margin = 10
    param_line_style = 'chls='

    def __init__(self, polls):
        Chart.__init__(self, '600x500', 'lxy')
        self.polls = polls
        self.avg = PollingAverage(polls)

    def build_url(self):
        ceil = 40.0
        url = Chart.base_url(self) + \
              Chart.add(self, Chart.param_axes, 'x,y') + '&' + \
              Chart.add(self, Chart.param_ranges, '1,0,' + str(len(self.polls)) + '|1,0,' + str(ceil)) + ',5&' + \
              Chart.add(self, Chart.param_scaling, '0,' + str(ceil)) + '&'

        data = colors = legends = line_style = ''

        for party in Party.all():
            data += '-1|'
            colors += party.color + ','
            legends += party.abbreviation + '|'
            line_style += '3|'
            for poll in self.polls:
                data += str(poll.percentage_of(party)) + ','
            data = data[0:-1] + '|'
        x_axis = ''
        i = 1
        for poll in self.polls:
            x_axis += '|' + str(i)
            i += 1

        return url + Chart.add(self, Chart.param_data, data[0:-1]) + '&' + \
                     Chart.add(self, Chart.param_colors, colors[0:-1]) + '&' + \
                     Chart.add(self, self.param_legends, legends[0:-1]) + '&' + \
                     Chart.add(self, 'chxl=0:', x_axis) + '&' + \
                     Chart.add(self, self.param_line_style, line_style[0:-1])


class BlockPieChart(Chart):

    def __init__(self, avg):
        Chart.__init__(self, '300x200', 'bvs')
        self.avg = avg

    def build_url(self):
        ceil = 50.0
        left_sum = self.avg.left_block_percentage()
        right_sum = self.avg.right_block_percentage()
        other_sum = self.avg.other_block_percentage()

        data = str(left_sum) + ',' + str(right_sum) + ',' + str(other_sum)
        colors = 'fd3131|85cbeb|adadad'
        labels = 'Soc. ' + ('%.1f' % left_sum) + '%|Borg. ' + ('%.1f' % right_sum) + '%|&Ouml;vr. ' + ('%.1f' % other_sum) + '%'

        return Chart.base_url(self) + '&' + \
               Chart.add(self, Chart.param_data, data) + '&' + \
               Chart.add(self, Chart.param_colors, colors) + '&' + \
               Chart.add(self, 'chbh=', 'a,30') + '&' + \
               Chart.add(self, Chart.param_axes, 'x,y') + '&' + \
               Chart.add(self, Chart.param_ranges, '0,0,0|1,0,' + str(ceil)) + '&' + \
               Chart.add(self, Chart.param_scaling, '0,' + str(ceil)) + '&' + \
               Chart.add(self, 'chtt=', 'Blockf&ouml;rdelning') + '&' + \
               Chart.add(self, Chart.param_labels, labels)


class SeatsChart(Chart):

    def __init__(self, avg):
        Chart.__init__(self, '300x200', 'bvs')
        self.avg = avg

    def build_url(self):
        ceil = 180.0
        left_sum = self.avg.left_block_percentage()
        right_sum = self.avg.right_block_percentage()
        other_sum = self.avg.other_block_percentage()

        #data = str(left_sum) + ',' + str(right_sum) + ',' + str(other_sum)
        # TODO
        data = '100,80,1|30,40,1|35,35,0|0,15,0' 
        colors = 'fd3131|85cbeb|adadad'
        labels = 'Soc.|Borg.|&Ouml;vr.'

        return Chart.base_url(self) + '&' + \
               Chart.add(self, Chart.param_data, data) + '&' + \
               Chart.add(self, Chart.param_colors, colors) + '&' + \
               Chart.add(self, 'chbh=', 'a,30') + '&' + \
               Chart.add(self, Chart.param_axes, 'x,y') + '&' + \
               Chart.add(self, Chart.param_ranges, '0,0,0|1,0,' + str(ceil)) + '&' + \
               Chart.add(self, Chart.param_scaling, '0,' + str(ceil)) + '&' + \
               Chart.add(self, 'chtt=', 'Mandatf&ouml;rdelning') + '&' + \
               Chart.add(self, Chart.param_labels, labels)
